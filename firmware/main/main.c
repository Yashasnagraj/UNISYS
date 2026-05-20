/**
 * @file    main.c
 * @brief   ResoScan firmware entry point. Brings up the full pipeline:
 *
 *               chirp_gen  (core 0, DAC + I2S DMA, 20-200 Hz log sweep)
 *                    |
 *                    v        Voice Coil  ===>  bone  ===>  vibration
 *                                                              |
 *                                                              v
 *              IIS3DWB <-- SPI @ 10 MHz, DMA ping-pong, INT1 DRDY
 *                    |
 *                    v
 *           sensor_task  (core 0, producer, ping-pong + float convert)
 *                    |
 *                    v   FreeRTOS stream buffer (4 frames capacity)
 *                    |
 *                    v
 *               fft_task  (core 1, esp_dsp FFT + peak + sub-bin interp)
 *                    |
 *                    v
 *             stiffness   (TSI = (f1 / f_healthy)^2 * 100, UART log)
 *
 *          Pipeline runs continuously. Scan trigger pulses the chirp; the
 *          DSP path runs always-on so we never miss a window.
 */

#include "config.h"
#include "chirp_gen.h"
#include "sensor_spi.h"
#include "fft_task.h"
#include "stiffness.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/stream_buffer.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"


static void boot_banner(void)
{
    ESP_LOGI(RS_TAG_MAIN, "==============================================");
    ESP_LOGI(RS_TAG_MAIN, " ResoScan firmware  v0.1                       ");
    ESP_LOGI(RS_TAG_MAIN, " Resonant Modal Spectroscopy bone diagnostic   ");
    ESP_LOGI(RS_TAG_MAIN, "==============================================");
    ESP_LOGI(RS_TAG_MAIN, " Physics target: f1 ~83 Hz (unhealed) -> "
                          "~101 Hz (healed)");
    ESP_LOGI(RS_TAG_MAIN, " Chirp band: %.0f - %.0f Hz (%s sweep, %u ms)",
             (double)RS_CHIRP_F_START_HZ, (double)RS_CHIRP_F_END_HZ,
             RS_CHIRP_USE_LOG_SWEEP ? "log" : "linear",
             (unsigned)RS_CHIRP_DURATION_MS);
    ESP_LOGI(RS_TAG_MAIN, " SPI %u MHz, ODR %.0f Hz, FFT N=%u, bin=%.2f Hz",
             (unsigned)(RS_SPI_CLOCK_HZ / 1000000),
             (double)RS_ACCEL_SAMPLE_RATE_HZ,
             (unsigned)RS_FFT_N, (double)RS_FFT_BIN_HZ);
    ESP_LOGI(RS_TAG_MAIN, "==============================================");
}


void app_main(void)
{
    /* NVS for calibration storage (f_healthy override, serial number, ...) */
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }

    boot_banner();

    /* --- DSP first (consumer must exist before producer streams) --- */
    ESP_ERROR_CHECK(fft_task_init());

    /* --- Sensor producer + stream buffer --- */
    StreamBufferHandle_t stream = NULL;
    ESP_ERROR_CHECK(sensor_spi_init(&stream));
    ESP_ERROR_CHECK(fft_task_start(stream));
    ESP_ERROR_CHECK(sensor_spi_start_task());

    /* --- Chirp excitation peripheral --- */
    ESP_ERROR_CHECK(chirp_gen_init());

    /* Main scan loop: trigger chirp every 2 s. DSP path runs continuously,
     * so each chirp injects a fresh excitation while the sensor + FFT keep
     * producing TSI estimates. */
    int cycle = 0;
    for (;;) {
        ESP_LOGI(RS_TAG_MAIN, "scan cycle %d ...", ++cycle);
        esp_err_t e = chirp_gen_start_async();
        if (e != ESP_OK) {
            ESP_LOGW(RS_TAG_MAIN, "chirp start: %s", esp_err_to_name(e));
        }
        /* Sweep + decay window */
        vTaskDelay(pdMS_TO_TICKS(RS_CHIRP_DURATION_MS + 1500));

        ESP_LOGI(RS_TAG_MAIN, "  current TSI = %.1f%%",
                 (double)stiffness_current_tsi());
    }
}
