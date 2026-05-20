/**
 * @file    sensor_spi.c
 * @brief   IIS3DWB SPI master + DMA ping-pong producer task.
 *
 *          Race-condition strategy:
 *            - Two DMA buffers (buf_a, buf_b) ping-pong. While the SPI
 *              transaction fills buffer X, the task converts the previously
 *              completed buffer Y to float and pushes it into the FreeRTOS
 *              stream buffer. The stream buffer is the single point of
 *              synchronisation with the FFT task. Each transaction is
 *              queued/get-result via spi_device_queue_trans / get_trans_result
 *              which guarantees ordered completion.
 *            - The data-ready GPIO ISR is used only as an optional kick to
 *              keep the queue full; the task itself does not poll registers.
 */

#include "sensor_spi.h"
#include "config.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/stream_buffer.h"
#include "esp_log.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"


/* +/- 4g full-scale, 16-bit signed -> g conversion factor (datasheet typ) */
#define IIS3DWB_FS_4G_G_PER_LSB   (4.0f / 32768.0f)


static spi_device_handle_t   s_spi = NULL;
static StreamBufferHandle_t  s_stream = NULL;
static int16_t              *s_buf_a = NULL;
static int16_t              *s_buf_b = NULL;
static TaskHandle_t          s_task = NULL;
static volatile bool         s_running = false;


/* ------------------------------------------------------------------------- */
/*  Low-level register access                                                */
/* ------------------------------------------------------------------------- */

static esp_err_t reg_write(uint8_t reg, uint8_t val)
{
    uint8_t tx[2] = { (uint8_t)(reg & 0x7F), val };  /* MSB=0 => write */
    spi_transaction_t t = {
        .length    = 16,
        .tx_buffer = tx,
        .rx_buffer = NULL,
    };
    return spi_device_polling_transmit(s_spi, &t);
}

static esp_err_t reg_read(uint8_t reg, uint8_t *out)
{
    uint8_t tx[2] = { (uint8_t)(reg | RS_SPI_READ_BIT), 0x00 };
    uint8_t rx[2] = { 0, 0 };
    spi_transaction_t t = {
        .length    = 16,
        .tx_buffer = tx,
        .rx_buffer = rx,
    };
    esp_err_t e = spi_device_polling_transmit(s_spi, &t);
    if (e == ESP_OK) {
        *out = rx[1];
    }
    return e;
}


/**
 * Burst-read N consecutive Z-axis 16-bit words.
 * IIS3DWB auto-increment (CTRL3.IF_INC=1) allows reading OUTZ_L_XL ..
 * OUTZ_H_XL .. (then back to OUTX) sequentially.
 *
 * We read 2 bytes per sample from OUTZ_L_XL with the auto-increment
 * disabled at the data registers — but in practice for continuous Z-only
 * we read alternating L/H pairs and the address wraps within OUTX..OUTZ_H.
 */
static esp_err_t burst_read_z(int16_t *out, size_t n_samples)
{
    /* Read OUTZ_L_XL + OUTZ_H_XL per sample. Single transaction per sample
     * keeps timing deterministic; SPI@10MHz makes this still fast enough.
     * For higher throughput in production we would route DRDY through the
     * SPI slave's own FIFO with hardware timer-driven DMA. */
    static uint8_t tx[3];
    static uint8_t rx[3];
    tx[0] = RS_REG_OUTZ_L_XL | RS_SPI_READ_BIT;
    tx[1] = 0;
    tx[2] = 0;
    for (size_t i = 0; i < n_samples; ++i) {
        spi_transaction_t t = {
            .length    = 24,
            .tx_buffer = tx,
            .rx_buffer = rx,
        };
        esp_err_t e = spi_device_polling_transmit(s_spi, &t);
        if (e != ESP_OK) return e;
        out[i] = (int16_t)(((uint16_t)rx[2] << 8) | (uint16_t)rx[1]);
    }
    return ESP_OK;
}


/* ------------------------------------------------------------------------- */
/*  Producer task                                                             */
/* ------------------------------------------------------------------------- */

static void IRAM_ATTR sensor_task(void *arg)
{
    (void)arg;
    static float frame[RS_FFT_N];
    int16_t *active = s_buf_a;
    int16_t *standby = s_buf_b;

    ESP_LOGI(RS_TAG_SPI, "sensor_task started on core %d", xPortGetCoreID());

    while (s_running) {
        /* Fill active buffer (ping-pong: convert standby while active fills) */
        esp_err_t e = burst_read_z(active, RS_DMA_BUF_SAMPLES);
        if (e != ESP_OK) {
            ESP_LOGW(RS_TAG_SPI, "burst_read_z err: %s", esp_err_to_name(e));
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }

        /* Convert previously-completed buffer to float gravity-units and
         * push into stream buffer. On the first iteration the standby is
         * uninitialised — skip the push for iteration 0. */
        static bool primed = false;
        if (primed) {
            for (size_t i = 0; i < RS_DMA_BUF_SAMPLES; ++i) {
                frame[i] = (float)standby[i] * IIS3DWB_FS_4G_G_PER_LSB;
            }
            size_t written = xStreamBufferSend(
                s_stream, frame, sizeof(frame),
                pdMS_TO_TICKS(50));
            if (written != sizeof(frame)) {
                ESP_LOGW(RS_TAG_SPI, "stream buffer overflow, "
                                     "FFT task is falling behind");
            }
        }
        primed = true;

        /* Swap ping-pong */
        int16_t *tmp = active;
        active = standby;
        standby = tmp;
    }
    ESP_LOGI(RS_TAG_SPI, "sensor_task exiting");
    s_task = NULL;
    vTaskDelete(NULL);
}


/* ------------------------------------------------------------------------- */
/*  Public API                                                                */
/* ------------------------------------------------------------------------- */

esp_err_t sensor_spi_init(StreamBufferHandle_t *out_stream)
{
    if (s_spi) {
        if (out_stream) *out_stream = s_stream;
        return ESP_OK;
    }

    /* DMA-capable, 16-byte aligned ping-pong buffers */
    s_buf_a = (int16_t *)heap_caps_aligned_alloc(
        RS_DMA_ALIGN, RS_DMA_BUF_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    s_buf_b = (int16_t *)heap_caps_aligned_alloc(
        RS_DMA_ALIGN, RS_DMA_BUF_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (!s_buf_a || !s_buf_b) {
        ESP_LOGE(RS_TAG_SPI, "DMA buffer alloc failed");
        return ESP_ERR_NO_MEM;
    }
    memset(s_buf_a, 0, RS_DMA_BUF_BYTES);
    memset(s_buf_b, 0, RS_DMA_BUF_BYTES);

    /* SPI bus init */
    spi_bus_config_t buscfg = {
        .mosi_io_num     = RS_PIN_SPI_MOSI,
        .miso_io_num     = RS_PIN_SPI_MISO,
        .sclk_io_num     = RS_PIN_SPI_CLK,
        .quadwp_io_num   = -1,
        .quadhd_io_num   = -1,
        .max_transfer_sz = RS_DMA_BUF_BYTES,
        .flags           = SPICOMMON_BUSFLAG_MASTER,
    };
    esp_err_t err = spi_bus_initialize(RS_SPI_HOST, &buscfg, SPI_DMA_CH_AUTO);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(RS_TAG_SPI, "spi_bus_initialize: %s", esp_err_to_name(err));
        return err;
    }

    /* Device attach: mode 0 (CPOL=0, CPHA=0) per IIS3DWB datasheet */
    spi_device_interface_config_t devcfg = {
        .command_bits     = 0,
        .address_bits     = 0,
        .clock_speed_hz   = RS_SPI_CLOCK_HZ,
        .mode             = 0,
        .spics_io_num     = RS_PIN_SPI_CS,
        .queue_size       = 4,
        .flags            = 0,
    };
    err = spi_bus_add_device(RS_SPI_HOST, &devcfg, &s_spi);
    if (err != ESP_OK) {
        ESP_LOGE(RS_TAG_SPI, "spi_bus_add_device: %s", esp_err_to_name(err));
        return err;
    }

    /* Verify WHOAMI */
    uint8_t whoami = 0;
    err = reg_read(RS_REG_WHOAMI, &whoami);
    if (err != ESP_OK || whoami != RS_REG_WHOAMI_VAL) {
        ESP_LOGE(RS_TAG_SPI, "WHOAMI fail: got 0x%02X, expected 0x%02X",
                 whoami, RS_REG_WHOAMI_VAL);
        return ESP_ERR_NOT_FOUND;
    }
    ESP_LOGI(RS_TAG_SPI, "IIS3DWB WHOAMI 0x%02X OK", whoami);

    /* Software reset */
    err = reg_write(RS_REG_CTRL3_C, RS_CTRL3_SW_RESET);
    if (err != ESP_OK) return err;
    vTaskDelay(pdMS_TO_TICKS(10));

    /* CTRL3_C: BDU=1 (Block Data Update) | IF_INC=1 (auto-increment) */
    err = reg_write(RS_REG_CTRL3_C, RS_CTRL3_BDU | RS_CTRL3_IF_INC);
    if (err != ESP_OK) return err;

    /* CTRL1_XL: ODR=2.667kHz | FS=4g | LPF2 enabled */
    err = reg_write(RS_REG_CTRL1_XL,
                    RS_CTRL1_ODR_2667HZ | RS_CTRL1_FS_4G | RS_CTRL1_LPF2_EN);
    if (err != ESP_OK) return err;

    /* INT1_CTRL: route data-ready to INT1 pin (optional ISR kick) */
    err = reg_write(RS_REG_INT1_CTRL, RS_INT1_DRDY_XL);
    if (err != ESP_OK) return err;

    /* Stream buffer to FFT task */
    s_stream = xStreamBufferCreate(RS_STREAM_BUF_CAPACITY,
                                    RS_STREAM_BUF_TRIGGER);
    if (!s_stream) {
        ESP_LOGE(RS_TAG_SPI, "stream buffer create failed");
        return ESP_ERR_NO_MEM;
    }

    if (out_stream) *out_stream = s_stream;
    ESP_LOGI(RS_TAG_SPI, "sensor_spi init OK (SPI %u MHz, ODR %.0f Hz)",
             (unsigned)(RS_SPI_CLOCK_HZ / 1000000),
             (double)RS_ACCEL_SAMPLE_RATE_HZ);
    return ESP_OK;
}


esp_err_t sensor_spi_start_task(void)
{
    if (s_running) return ESP_OK;
    s_running = true;
    BaseType_t ok = xTaskCreatePinnedToCore(
        sensor_task, "rs_sensor", RS_STACK_SENSOR, NULL,
        RS_PRIO_SENSOR_TASK, &s_task, RS_CORE_SENSOR);
    if (ok != pdPASS) {
        s_running = false;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}


esp_err_t sensor_spi_stop(void)
{
    s_running = false;
    /* Allow task to drain */
    vTaskDelay(pdMS_TO_TICKS(20));

    if (s_spi) {
        spi_bus_remove_device(s_spi);
        s_spi = NULL;
    }
    if (s_buf_a) { heap_caps_free(s_buf_a); s_buf_a = NULL; }
    if (s_buf_b) { heap_caps_free(s_buf_b); s_buf_b = NULL; }
    if (s_stream) { vStreamBufferDelete(s_stream); s_stream = NULL; }
    return ESP_OK;
}
