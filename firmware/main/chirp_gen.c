/**
 * @file    chirp_gen.c
 * @brief   Voice-coil chirp generator — log sweep 20-200 Hz over 500 ms.
 *
 *          ESP-IDF v5 dac_continuous API: pre-loaded DMA descriptors stream
 *          the entire chirp waveform to GPIO17 without CPU intervention.
 *
 *          Why log sweep? Equal energy per octave keeps SNR uniform across
 *          the band, important since the tibial f1 trajectory spans roughly
 *          one octave (~83 Hz -> ~101 Hz) and we want consistent excitation
 *          across the whole healing window.
 */

#include "chirp_gen.h"
#include "config.h"

#include <math.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_attr.h"
#include "driver/dac_continuous.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

static dac_continuous_handle_t s_dac_handle = NULL;
static uint8_t *s_chirp_buf = NULL;            /* WORD_ALIGNED DMA-capable */
static size_t   s_chirp_buf_bytes = 0;
static volatile bool s_running = false;
static SemaphoreHandle_t s_done_sem = NULL;


/**
 * Precompute the 8-bit unsigned DAC samples for a log sweep from
 * f_start to f_end. DAC on ESP32-S3 is 8-bit (0..255), biased at 128 for
 * AC coupling through the Class-D amplifier.
 *
 * Phase accumulated via trapezoid integration:
 *   phi(t) = 2*pi * integral_0^t f(tau) d_tau
 * For log sweep f(t) = f0 * (f1/f0)^(t/T):
 *   integral = f0 * T / ln(f1/f0) * ((f1/f0)^(t/T) - 1)
 */
static void precompute_chirp(uint8_t *buf, uint32_t n_samples)
{
    const float fs = (float)RS_DAC_SAMPLE_RATE_HZ;
    const float duration = (float)RS_CHIRP_DURATION_MS / 1000.0f;
    const float f0 = RS_CHIRP_F_START_HZ;
    const float f1 = RS_CHIRP_F_END_HZ;
    const float amp = RS_CHIRP_AMPLITUDE;

#if RS_CHIRP_USE_LOG_SWEEP
    const float k = logf(f1 / f0);
#endif

    for (uint32_t i = 0; i < n_samples; ++i) {
        float t = (float)i / fs;
        float phi;
#if RS_CHIRP_USE_LOG_SWEEP
        phi = 2.0f * M_PI * f0 * duration / k * (expf(k * t / duration) - 1.0f);
#else
        /* Linear sweep f(t) = f0 + (f1-f0) * t/T */
        phi = 2.0f * M_PI * (f0 * t + (f1 - f0) * t * t / (2.0f * duration));
#endif
        /* Hanning envelope on first/last 5% to suppress click artifacts */
        float env = 1.0f;
        float ramp = 0.05f * (float)n_samples;
        if ((float)i < ramp) {
            env = 0.5f * (1.0f - cosf(M_PI * (float)i / ramp));
        } else if ((float)i > (float)n_samples - ramp) {
            float r = (float)(n_samples - i) / ramp;
            env = 0.5f * (1.0f - cosf(M_PI * r));
        }

        float s = amp * env * sinf(phi);
        int v = (int)(127.5f + 127.5f * s);
        if (v < 0)   v = 0;
        if (v > 255) v = 255;
        buf[i] = (uint8_t)v;
    }
}


static IRAM_ATTR bool on_dac_done_cb(dac_continuous_handle_t handle,
                                     const dac_event_data_t *event,
                                     void *user_data)
{
    BaseType_t hpw = pdFALSE;
    s_running = false;
    if (s_done_sem) {
        xSemaphoreGiveFromISR(s_done_sem, &hpw);
    }
    return hpw == pdTRUE;
}


esp_err_t chirp_gen_init(void)
{
    if (s_chirp_buf) {
        return ESP_OK;  /* already initialised */
    }

    s_chirp_buf_bytes = RS_CHIRP_N_SAMPLES;
    /* DMA-capable, 16-byte aligned */
    s_chirp_buf = (uint8_t *)heap_caps_aligned_alloc(
        RS_DMA_ALIGN, s_chirp_buf_bytes,
        MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    if (!s_chirp_buf) {
        ESP_LOGE(RS_TAG_CHIRP, "DMA buffer alloc failed (%u bytes)",
                 (unsigned)s_chirp_buf_bytes);
        return ESP_ERR_NO_MEM;
    }

    precompute_chirp(s_chirp_buf, RS_CHIRP_N_SAMPLES);

    s_done_sem = xSemaphoreCreateBinary();
    if (!s_done_sem) {
        heap_caps_free(s_chirp_buf);
        s_chirp_buf = NULL;
        return ESP_ERR_NO_MEM;
    }

    dac_continuous_config_t cfg = {
        .chan_mask = DAC_CHANNEL_MASK_CH0,        /* GPIO17 on S3 */
        .desc_num  = 4,
        .buf_size  = s_chirp_buf_bytes,
        .freq_hz   = RS_DAC_SAMPLE_RATE_HZ,
        .offset    = 0,
        .clk_src   = DAC_DIGI_CLK_SRC_DEFAULT,
        .chan_mode = DAC_CHANNEL_MODE_SIMUL,
    };
    esp_err_t err = dac_continuous_new_channels(&cfg, &s_dac_handle);
    if (err != ESP_OK) {
        ESP_LOGE(RS_TAG_CHIRP, "dac_continuous_new_channels failed: %s",
                 esp_err_to_name(err));
        return err;
    }

    dac_event_callbacks_t cbs = {
        .on_convert_done = NULL,
        .on_stop = on_dac_done_cb,
    };
    err = dac_continuous_register_event_callback(s_dac_handle, &cbs, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(RS_TAG_CHIRP, "callback register failed: %s",
                 esp_err_to_name(err));
        return err;
    }

    err = dac_continuous_enable(s_dac_handle);
    if (err != ESP_OK) {
        ESP_LOGE(RS_TAG_CHIRP, "dac_continuous_enable failed: %s",
                 esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(RS_TAG_CHIRP,
             "init OK: %u samples @ %u Hz, %.1f-%.1f Hz %s sweep, %u ms",
             (unsigned)RS_CHIRP_N_SAMPLES, (unsigned)RS_DAC_SAMPLE_RATE_HZ,
             (double)RS_CHIRP_F_START_HZ, (double)RS_CHIRP_F_END_HZ,
             RS_CHIRP_USE_LOG_SWEEP ? "log" : "linear",
             (unsigned)RS_CHIRP_DURATION_MS);
    return ESP_OK;
}


esp_err_t chirp_gen_start_async(void)
{
    if (!s_chirp_buf || !s_dac_handle) {
        return ESP_ERR_INVALID_STATE;
    }
    if (s_running) {
        return ESP_ERR_INVALID_STATE;
    }
    s_running = true;
    /* Write the full chirp into DMA descriptors. Non-blocking once queued. */
    size_t written = 0;
    esp_err_t err = dac_continuous_write_asynchronously(
        s_dac_handle, s_chirp_buf, s_chirp_buf_bytes,
        s_chirp_buf, s_chirp_buf_bytes, &written);
    if (err != ESP_OK) {
        ESP_LOGW(RS_TAG_CHIRP, "async write err: %s", esp_err_to_name(err));
        s_running = false;
        return err;
    }
    return ESP_OK;
}


bool chirp_gen_is_running(void)
{
    return s_running;
}


esp_err_t chirp_gen_deinit(void)
{
    if (s_dac_handle) {
        dac_continuous_disable(s_dac_handle);
        dac_continuous_del_channels(s_dac_handle);
        s_dac_handle = NULL;
    }
    if (s_chirp_buf) {
        heap_caps_free(s_chirp_buf);
        s_chirp_buf = NULL;
    }
    if (s_done_sem) {
        vSemaphoreDelete(s_done_sem);
        s_done_sem = NULL;
    }
    return ESP_OK;
}
