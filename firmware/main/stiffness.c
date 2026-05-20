/**
 * @file    stiffness.c
 * @brief   TSI tracking with simple exponential smoothing + UART log.
 *
 *          The FFT task may produce one f1 estimate every ~400 ms (1024
 *          samples / 2667 Hz). To avoid jitter from spurious peaks the
 *          frequency is exponentially smoothed (alpha = 0.3) before TSI
 *          conversion. A lower SNR threshold rejects clearly invalid frames.
 */

#include "stiffness.h"
#include "config.h"

#include <stdio.h>
#include <math.h>
#include "esp_log.h"


/* Power-floor: PSD bin power must exceed this to be considered a real peak.
 * Tuned empirically; in practice this is calibrated against a known healthy
 * baseline scan during device commissioning. */
#define STIFFNESS_PSD_FLOOR        1e-6f

#define STIFFNESS_SMOOTHING_ALPHA  0.30f


static float s_f_healthy_hz = RS_TIBIA_F_HEALTHY_HZ;
static float s_f1_smoothed_hz = 0.0f;
static float s_tsi_pct = 0.0f;
static bool  s_primed = false;


static const char *recommendation_for_tsi(float tsi)
{
    if (tsi >= RS_TSI_FULL_WB_PCT)    return "FULL weight-bearing";
    if (tsi >= RS_TSI_PARTIAL_WB_PCT) return "PARTIAL weight-bearing";
    return "NON weight-bearing";
}


void stiffness_update(float f1_hz, float power)
{
    if (power < STIFFNESS_PSD_FLOOR) {
        ESP_LOGW(RS_TAG_STIFF, "rejected: power %.2e below floor", power);
        return;
    }
    if (f1_hz < RS_PEAK_SEARCH_LO_HZ || f1_hz > RS_PEAK_SEARCH_HI_HZ) {
        ESP_LOGW(RS_TAG_STIFF, "rejected: f1 %.1f Hz out of search band",
                 f1_hz);
        return;
    }

    if (!s_primed) {
        s_f1_smoothed_hz = f1_hz;
        s_primed = true;
    } else {
        s_f1_smoothed_hz = STIFFNESS_SMOOTHING_ALPHA * f1_hz +
                           (1.0f - STIFFNESS_SMOOTHING_ALPHA) * s_f1_smoothed_hz;
    }

    /* TSI = (f1 / f_healthy)^2 * 100 */
    float ratio = s_f1_smoothed_hz / s_f_healthy_hz;
    s_tsi_pct = ratio * ratio * 100.0f;
    if (s_tsi_pct > 200.0f) s_tsi_pct = 200.0f;  /* clamp implausibles */

    ESP_LOGI(RS_TAG_STIFF,
             "f1=%.2f Hz (smoothed=%.2f Hz)  TSI=%.1f%%  -> %s",
             f1_hz, s_f1_smoothed_hz, s_tsi_pct,
             recommendation_for_tsi(s_tsi_pct));
}


float stiffness_current_tsi(void)
{
    return s_tsi_pct;
}


void stiffness_set_f_healthy(float hz)
{
    if (hz > 1.0f && hz < 500.0f) {
        s_f_healthy_hz = hz;
        ESP_LOGI(RS_TAG_STIFF, "f_healthy set to %.2f Hz", hz);
    }
}
