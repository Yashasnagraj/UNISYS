/**
 * @file    fft_task.h
 * @brief   FreeRTOS FFT consumer task — esp_dsp 1024-point radix-2 FFT,
 *          PSD, peak detection in 20-200 Hz band, TSI handoff to stiffness.
 */

#ifndef RESOSCAN_FFT_TASK_H
#define RESOSCAN_FFT_TASK_H

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/stream_buffer.h"

/**
 * Initialise esp_dsp FFT tables, precompute Hanning window, allocate
 * working buffers. Must be called once before fft_task_start().
 */
esp_err_t fft_task_init(void);

/**
 * Start the FFT consumer task pinned to RS_CORE_DSP. It blocks on
 * @p in_stream, reading RS_FFT_N float samples per cycle, and writes the
 * detected dominant frequency to the stiffness module.
 */
esp_err_t fft_task_start(StreamBufferHandle_t in_stream);

#endif /* RESOSCAN_FFT_TASK_H */
