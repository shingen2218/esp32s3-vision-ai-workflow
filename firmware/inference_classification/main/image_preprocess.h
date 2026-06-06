#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#define MODEL_INPUT_WIDTH 96
#define MODEL_INPUT_HEIGHT 96
#define MODEL_INPUT_CHANNELS 3

esp_err_t preprocess_jpeg_to_int8(const uint8_t *jpeg, size_t jpeg_len, int8_t *output, size_t output_len);
