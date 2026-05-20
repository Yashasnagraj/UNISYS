/**
 * @file    sensor_spi.h
 * @brief   IIS3DWB MEMS accelerometer over SPI master with DMA ping-pong.
 *
 *          Replaces the previous blocking-I2C approach. SPI @ 10 MHz lifts
 *          bandwidth ~25x over I2C @ 400 kHz; DMA ping-pong eliminates CPU
 *          stalls during continuous acquisition.
 */

#ifndef RESOSCAN_SENSOR_SPI_H
#define RESOSCAN_SENSOR_SPI_H

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/stream_buffer.h"
#include <stdint.h>
#include <stddef.h>

/**
 * Initialize SPI bus, attach IIS3DWB device, configure registers
 * (WHOAMI check -> SW reset -> CTRL3 (BDU+IF_INC) -> CTRL1 (ODR+FS) ->
 * INT1 (DRDY) routing). Allocates two 16-byte-aligned DMA buffers.
 *
 * @param  out_stream  receives the FreeRTOS stream buffer handle into which
 *                     the sensor task pushes float32 Z-axis samples.
 *                     The FFT task is the sole consumer.
 */
esp_err_t sensor_spi_init(StreamBufferHandle_t *out_stream);

/**
 * Begin the producer task pinned to RS_CORE_SENSOR. The task issues
 * non-blocking SPI burst reads of RS_DMA_BUF_SAMPLES Z-axis words at a time,
 * converts to float (gravity-units), and writes them into the stream buffer.
 */
esp_err_t sensor_spi_start_task(void);

/**
 * Stop the producer task and release SPI device + DMA buffers.
 */
esp_err_t sensor_spi_stop(void);

#endif /* RESOSCAN_SENSOR_SPI_H */
