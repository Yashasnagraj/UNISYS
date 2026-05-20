/**
 * @file    config.h
 * @brief   ResoScan firmware-wide configuration: pinout, clocking, buffers,
 *          frequencies, register addresses, FreeRTOS topology.
 *
 *          All magic numbers live here. All bitmask flags use (1U << N).
 *          Implementation files include only this header for tuning.
 */

#ifndef RESOSCAN_CONFIG_H
#define RESOSCAN_CONFIG_H

#include <stdint.h>
#include "driver/gpio.h"
#include "driver/spi_common.h"

/* ============================================================================
 *  GPIO PINOUT — ESP32-S3 reference design
 * ========================================================================= */

/* IIS3DWB MEMS accelerometer over SPI (SPI2_HOST / FSPI on ESP32-S3) */
#define RS_SPI_HOST            SPI2_HOST
#define RS_PIN_SPI_MOSI        GPIO_NUM_11
#define RS_PIN_SPI_MISO        GPIO_NUM_13
#define RS_PIN_SPI_CLK         GPIO_NUM_12
#define RS_PIN_SPI_CS          GPIO_NUM_10
#define RS_PIN_SPI_INT1        GPIO_NUM_14   /* data-ready IRQ */

/* DAC + Class-D amplifier driving Voice Coil Actuator */
#define RS_PIN_DAC_OUT         GPIO_NUM_17   /* DAC channel 1 (GPIO17 on S3) */
#define RS_PIN_AMP_SHUTDOWN    GPIO_NUM_18   /* amplifier shutdown control */

/* Status LEDs (optional) */
#define RS_PIN_LED_SCAN        GPIO_NUM_2
#define RS_PIN_LED_DONE        GPIO_NUM_3

/* ============================================================================
 *  CLOCKING & SAMPLE RATES
 * ========================================================================= */

/* SPI master clock: 10 MHz is well within IIS3DWB max (10 MHz spec) and gives
 * 1.25 MB/s raw throughput — orders of magnitude over what we need.
 * I2C @ 400 kHz × 16 bits would cap at ~25 kS/s; SPI lifts that ceiling. */
#define RS_SPI_CLOCK_HZ        (10 * 1000 * 1000)

/* IIS3DWB ODR options (CTRL1_XL bits): use 2.667 kHz (closest to 2.0-3.2 kHz
 * target). At 16-bit × 1 axis × 2667 Hz = ~5.3 KB/s — trivial for SPI@10MHz. */
#define RS_ACCEL_SAMPLE_RATE_HZ   2667.0f

/* DAC continuous output rate for chirp synthesis. 8 kHz is 40× the 200 Hz
 * Nyquist, ensuring clean sweep with negligible aliasing. */
#define RS_DAC_SAMPLE_RATE_HZ     8000

/* ============================================================================
 *  CHIRP EXCITATION (Physics Pivot: 20-200 Hz fundamental flexural mode)
 *
 *  Tibial fundamental f1 range: ~83 Hz unhealed -> ~101 Hz healed (Cunningham
 *  1990, Nakatsuchi 1996). Sweeping 20-200 Hz covers the full healing
 *  trajectory with margin and avoids wasted energy in higher modes that the
 *  fundamental-mode-tracking pipeline does not use.
 * ========================================================================= */

#define RS_CHIRP_F_START_HZ       20.0f
#define RS_CHIRP_F_END_HZ         200.0f
#define RS_CHIRP_DURATION_MS      500
#define RS_CHIRP_AMPLITUDE        0.85f    /* 0..1, leaves DAC headroom */
#define RS_CHIRP_USE_LOG_SWEEP    1        /* 1 = log, 0 = linear */

/* Total pre-computed sample count */
#define RS_CHIRP_N_SAMPLES \
    ((uint32_t)(RS_DAC_SAMPLE_RATE_HZ * RS_CHIRP_DURATION_MS / 1000))

/* ============================================================================
 *  FFT / DSP PIPELINE
 * ========================================================================= */

/* 1024-point radix-2 FFT.
 * At fs = 2667 Hz, frequency resolution = 2667/1024 ~= 2.6 Hz — fine enough
 * to resolve the ~18 Hz unhealed -> healed shift. */
#define RS_FFT_N                  1024
#define RS_FFT_BIN_HZ             (RS_ACCEL_SAMPLE_RATE_HZ / (float)RS_FFT_N)

/* Peak search band */
#define RS_PEAK_SEARCH_LO_HZ      20.0f
#define RS_PEAK_SEARCH_HI_HZ      200.0f

/* Healthy tibial baseline (NVS-overridable per patient via calibration tool) */
#define RS_TIBIA_F_HEALTHY_HZ     101.0f

/* TSI healing thresholds (matches simulator clinical_metrics.py) */
#define RS_TSI_FULL_WB_PCT        80.0f    /* full weight-bear above this */
#define RS_TSI_PARTIAL_WB_PCT     60.0f    /* partial above this */

/* ============================================================================
 *  DMA BUFFERS (ping-pong)
 *
 *  Two equal-size buffers; while DMA fills A, FFT task consumes B (and vice
 *  versa). Allocated via heap_caps_aligned_alloc(16, ..., MALLOC_CAP_DMA).
 *  16-byte alignment satisfies the strictest ESP32 DMA requirement.
 * ========================================================================= */

#define RS_DMA_BUF_SAMPLES        RS_FFT_N             /* 1024 samples / buffer */
#define RS_DMA_BUF_BYTES          (RS_DMA_BUF_SAMPLES * sizeof(int16_t))
#define RS_DMA_ALIGN              16

/* Stream buffer (FreeRTOS) capacity: 4 chunks of FFT-sized float frames */
#define RS_STREAM_BUF_CAPACITY    (4 * RS_FFT_N * sizeof(float))
#define RS_STREAM_BUF_TRIGGER     (RS_FFT_N * sizeof(float))

/* ============================================================================
 *  FREERTOS TOPOLOGY (dual-core)
 * ========================================================================= */

#define RS_CORE_SENSOR            0      /* SPI/DMA pinned here */
#define RS_CORE_DSP               1      /* FFT/PSD pinned here */

#define RS_PRIO_SENSOR_TASK       10
#define RS_PRIO_FFT_TASK          9
#define RS_PRIO_CHIRP_TASK        8

#define RS_STACK_SENSOR           4096
#define RS_STACK_FFT              6144   /* esp_dsp working area */
#define RS_STACK_CHIRP            3072

/* ============================================================================
 *  IIS3DWB REGISTER MAP (subset — only what we use)
 *  Datasheet rev 4, STMicroelectronics
 * ========================================================================= */

#define RS_REG_WHOAMI             0x0F
#define RS_REG_WHOAMI_VAL         0x7B    /* IIS3DWB ID */

#define RS_REG_CTRL1_XL           0x10    /* accel ctrl: ODR, FS */
#define RS_REG_CTRL3_C            0x12    /* BDU, auto-increment, IF-INC */
#define RS_REG_CTRL4_C            0x13    /* INT2-on-INT1 routing, sleep, etc. */
#define RS_REG_INT1_CTRL          0x0D    /* INT1 pin routing */

#define RS_REG_OUTZ_L_XL          0x2C    /* Z low byte */
#define RS_REG_OUTZ_H_XL          0x2D    /* Z high byte */
#define RS_REG_OUTX_L_XL          0x28    /* burst-read start (X low) */

/* CTRL1_XL bitfield (ODR_XL[3:0] | FS_XL[1:0] | LPF2_XL_EN | _reserved) */
#define RS_CTRL1_ODR_2667HZ       (0xA0)  /* ODR_XL = 1010 (placeholder; verify
                                              against IIS3DWB rev — single ODR */
#define RS_CTRL1_FS_4G            (0x08)  /* +/- 4 g full-scale */
#define RS_CTRL1_LPF2_EN          (1U << 1)

/* CTRL3_C bits */
#define RS_CTRL3_BDU              (1U << 6)  /* Block Data Update */
#define RS_CTRL3_IF_INC           (1U << 2)  /* register auto-increment */
#define RS_CTRL3_SW_RESET         (1U << 0)

/* INT1_CTRL bits */
#define RS_INT1_DRDY_XL           (1U << 0)  /* data-ready on INT1 */

/* SPI read/write bit (R/W bit 7 of register address: 1 = read, 0 = write) */
#define RS_SPI_READ_BIT           (1U << 7)

/* ============================================================================
 *  LOG TAGS (single source of truth for ESP_LOGI/E/W)
 * ========================================================================= */

#define RS_TAG_MAIN               "resoscan"
#define RS_TAG_CHIRP              "rs.chirp"
#define RS_TAG_SPI                "rs.spi"
#define RS_TAG_FFT                "rs.fft"
#define RS_TAG_STIFF              "rs.stiff"

#endif /* RESOSCAN_CONFIG_H */
