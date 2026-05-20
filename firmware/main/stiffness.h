/**
 * @file    stiffness.h
 * @brief   Tibial Stiffness Index (TSI) computation and logging.
 *
 *          TSI = (f1 / f_healthy)^2 * 100      [%]
 *
 *          Per Pelker 1983, Cunningham 1990, Nakatsuchi 1996: stiffness k is
 *          proportional to f^2 (since f = (1/2pi) * sqrt(k/m) for an SDOF
 *          oscillator), so the squared-frequency ratio is a clinically
 *          meaningful proxy for mechanical healing.
 */

#ifndef RESOSCAN_STIFFNESS_H
#define RESOSCAN_STIFFNESS_H

#include <stdbool.h>

/**
 * Called by the FFT task each time a new f1 estimate is available.
 *
 * @param  f1_hz   dominant frequency estimate in the 20-200 Hz band
 * @param  power   PSD power at the peak (for SNR-based reject logic)
 */
void stiffness_update(float f1_hz, float power);

/**
 * @return current TSI percentage (most-recent estimate).
 */
float stiffness_current_tsi(void);

/**
 * Override the healthy reference frequency (e.g., from NVS calibration).
 * Default is RS_TIBIA_F_HEALTHY_HZ.
 */
void stiffness_set_f_healthy(float hz);

#endif /* RESOSCAN_STIFFNESS_H */
