/**
 * @file    chirp_gen.h
 * @brief   Voice-coil chirp excitation via DAC + I2S DMA (20-200 Hz sweep).
 *
 *          The chirp waveform is precomputed once at boot into a DMA-aligned
 *          buffer and pushed out by the dac_continuous peripheral. The CPU is
 *          uninvolved during playback — no blocking, no jitter.
 */

#ifndef RESOSCAN_CHIRP_GEN_H
#define RESOSCAN_CHIRP_GEN_H

#include "esp_err.h"
#include <stdbool.h>

/**
 * Allocate DMA buffer, precompute chirp samples, initialize dac_continuous.
 * Must be called once at boot before chirp_gen_start_async().
 */
esp_err_t chirp_gen_init(void);

/**
 * Begin the 20-200 Hz sweep. Returns immediately; playback runs in DMA.
 * Caller may sleep for RS_CHIRP_DURATION_MS to await completion, or run
 * other tasks in the meantime. Safe to invoke repeatedly.
 */
esp_err_t chirp_gen_start_async(void);

/**
 * @return true while DMA playback is in progress.
 */
bool chirp_gen_is_running(void);

/**
 * Release DAC peripheral and free DMA buffer. Test-time hook; not used in
 * the steady-state production loop.
 */
esp_err_t chirp_gen_deinit(void);

#endif /* RESOSCAN_CHIRP_GEN_H */
