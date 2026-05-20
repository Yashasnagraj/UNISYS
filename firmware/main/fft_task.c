/**
 * @file    fft_task.c
 * @brief   esp_dsp single-precision FFT task pinned to core 1.
 *
 *          Flow per cycle:
 *            1. xStreamBufferReceive(RS_FFT_N float samples)
 *            2. detrend (remove DC bias)
 *            3. apply Hanning window
 *            4. interleave into complex buffer (real, imag=0)
 *            5. dsps_fft2r_fc32 (radix-2 in-place)
 *            6. bit-reverse re-order
 *            7. compute PSD: |X[k]|^2
 *            8. find peak bin in [RS_PEAK_SEARCH_LO_HZ, RS_PEAK_SEARCH_HI_HZ]
 *            9. quadratic interpolation around peak bin for sub-bin precision
 *           10. hand off f1 to stiffness module
 *
 *          The complex working buffer is 2*N floats (8 KB). It is allocated
 *          via heap_caps_aligned_alloc so DMA / SIMD requirements are met.
 */

#include "fft_task.h"
#include "config.h"
#include "stiffness.h"

#include <math.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/stream_buffer.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_attr.h"
#include "esp_dsp.h"


static float *s_window = NULL;        /* RS_FFT_N */
static float *s_y_cf  = NULL;         /* 2 * RS_FFT_N (complex interleaved) */
static StreamBufferHandle_t s_in = NULL;
static TaskHandle_t s_task = NULL;


/**
 * Quadratic peak interpolation. Given three log-magnitudes around the peak
 * bin k, returns the fractional bin offset delta such that the true peak is
 * at (k + delta). Stable across [-1, +1].
 */
static inline float quad_interp(float ym1, float y0, float yp1)
{
    float denom = (ym1 - 2.0f * y0 + yp1);
    if (fabsf(denom) < 1e-12f) return 0.0f;
    return 0.5f * (ym1 - yp1) / denom;
}


static void IRAM_ATTR fft_task_fn(void *arg)
{
    (void)arg;
    static float frame[RS_FFT_N];
    static float psd[RS_FFT_N / 2];

    ESP_LOGI(RS_TAG_FFT, "fft_task started on core %d", xPortGetCoreID());

    const int k_lo = (int)(RS_PEAK_SEARCH_LO_HZ / RS_FFT_BIN_HZ);
    const int k_hi = (int)(RS_PEAK_SEARCH_HI_HZ / RS_FFT_BIN_HZ);
    const int n_half = RS_FFT_N / 2;
    const int k_lo_clamped = k_lo < 1 ? 1 : k_lo;
    const int k_hi_clamped = k_hi > n_half - 2 ? n_half - 2 : k_hi;

    for (;;) {
        size_t got = xStreamBufferReceive(s_in, frame, sizeof(frame),
                                          portMAX_DELAY);
        if (got != sizeof(frame)) {
            ESP_LOGW(RS_TAG_FFT, "short read: %u of %u",
                     (unsigned)got, (unsigned)sizeof(frame));
            continue;
        }

        /* Detrend (subtract mean) */
        float mean = 0.0f;
        for (int i = 0; i < RS_FFT_N; ++i) mean += frame[i];
        mean /= (float)RS_FFT_N;
        for (int i = 0; i < RS_FFT_N; ++i) frame[i] -= mean;

        /* Apply window + interleave as complex (Re, Im=0) */
        for (int i = 0; i < RS_FFT_N; ++i) {
            s_y_cf[2 * i + 0] = frame[i] * s_window[i];
            s_y_cf[2 * i + 1] = 0.0f;
        }

        /* In-place radix-2 FFT */
        dsps_fft2r_fc32(s_y_cf, RS_FFT_N);
        dsps_bit_rev_fc32(s_y_cf, RS_FFT_N);

        /* PSD on positive freqs */
        for (int k = 0; k < n_half; ++k) {
            float re = s_y_cf[2 * k + 0];
            float im = s_y_cf[2 * k + 1];
            psd[k] = re * re + im * im;
        }

        /* Peak search within the 20-200 Hz band */
        int peak_k = k_lo_clamped;
        float peak_v = psd[k_lo_clamped];
        for (int k = k_lo_clamped + 1; k <= k_hi_clamped; ++k) {
            if (psd[k] > peak_v) {
                peak_v = psd[k];
                peak_k = k;
            }
        }

        /* Sub-bin precision via parabolic interpolation on log-magnitude */
        float ym1 = logf(psd[peak_k - 1] + 1e-20f);
        float y0  = logf(psd[peak_k]     + 1e-20f);
        float yp1 = logf(psd[peak_k + 1] + 1e-20f);
        float delta = quad_interp(ym1, y0, yp1);
        float f1_hz = ((float)peak_k + delta) * RS_FFT_BIN_HZ;

        /* Hand off */
        stiffness_update(f1_hz, peak_v);
    }
}


esp_err_t fft_task_init(void)
{
    if (s_window) return ESP_OK;

    /* Allocate aligned buffers */
    s_window = (float *)heap_caps_aligned_alloc(
        RS_DMA_ALIGN, RS_FFT_N * sizeof(float), MALLOC_CAP_INTERNAL);
    s_y_cf = (float *)heap_caps_aligned_alloc(
        RS_DMA_ALIGN, 2 * RS_FFT_N * sizeof(float), MALLOC_CAP_INTERNAL);
    if (!s_window || !s_y_cf) {
        ESP_LOGE(RS_TAG_FFT, "buffer alloc failed");
        return ESP_ERR_NO_MEM;
    }

    /* Init esp_dsp tables */
    esp_err_t e = dsps_fft2r_init_fc32(NULL, CONFIG_DSP_MAX_FFT_SIZE);
    if (e != ESP_OK) {
        ESP_LOGE(RS_TAG_FFT, "dsps_fft2r_init_fc32: %s", esp_err_to_name(e));
        return e;
    }

    /* Precompute Hanning window */
    dsps_wind_hann_f32(s_window, RS_FFT_N);

    ESP_LOGI(RS_TAG_FFT, "fft_task init OK: N=%u, bin=%.2f Hz, "
                          "search [%.0f, %.0f] Hz",
             (unsigned)RS_FFT_N, (double)RS_FFT_BIN_HZ,
             (double)RS_PEAK_SEARCH_LO_HZ, (double)RS_PEAK_SEARCH_HI_HZ);
    return ESP_OK;
}


esp_err_t fft_task_start(StreamBufferHandle_t in_stream)
{
    if (!in_stream) return ESP_ERR_INVALID_ARG;
    if (s_task)     return ESP_OK;
    s_in = in_stream;
    BaseType_t ok = xTaskCreatePinnedToCore(
        fft_task_fn, "rs_fft", RS_STACK_FFT, NULL,
        RS_PRIO_FFT_TASK, &s_task, RS_CORE_DSP);
    return (ok == pdPASS) ? ESP_OK : ESP_ERR_NO_MEM;
}
