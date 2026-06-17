#include "image_preprocess.h"

#include <math.h>
#include <stdlib.h>

#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "img_converters.h"

static const char *TAG = "image_preprocess";

static int clamp_int(int value, int min_value, int max_value)
{
    if (value < min_value) return min_value;
    if (value > max_value) return max_value;
    return value;
}

static int8_t quantize_rgb_value(uint8_t value, float input_scale, int input_zero_point)
{
    if (input_scale <= 0.0f) {
        input_scale = 1.0f;
    }
    int quantized = (int)lrintf((float)value / input_scale) + input_zero_point;
    return (int8_t)clamp_int(quantized, -128, 127);
}

esp_err_t preprocess_jpeg_to_int8(
    const uint8_t *jpeg,
    size_t jpeg_len,
    int8_t *output,
    size_t output_len,
    float input_scale,
    int input_zero_point)
{
    const size_t model_input_len = MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS;
    if (output_len < model_input_len) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (!jpeg || jpeg_len == 0 || !output) {
        return ESP_ERR_INVALID_ARG;
    }

    const int source_width = 320;
    const int source_height = 240;
    const size_t rgb_len = source_width * source_height * MODEL_INPUT_CHANNELS;
    uint8_t *rgb = (uint8_t *)heap_caps_malloc(rgb_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!rgb) {
        rgb = (uint8_t *)heap_caps_malloc(rgb_len, MALLOC_CAP_8BIT);
    }
    if (!rgb) {
        ESP_LOGE(TAG, "failed to allocate RGB buffer (%u bytes)", rgb_len);
        return ESP_ERR_NO_MEM;
    }

    if (!fmt2rgb888(jpeg, jpeg_len, PIXFORMAT_JPEG, rgb)) {
        ESP_LOGE(TAG, "JPEG decode to RGB888 failed");
        free(rgb);
        return ESP_FAIL;
    }

    const float source_aspect = (float)source_width / (float)source_height;
    const float target_aspect = (float)MODEL_INPUT_WIDTH / (float)MODEL_INPUT_HEIGHT;
    int crop_x = 0;
    int crop_y = 0;
    int crop_width = source_width;
    int crop_height = source_height;
    if (source_aspect > target_aspect) {
        crop_width = (int)((float)source_height * target_aspect);
        crop_x = (source_width - crop_width) / 2;
    } else if (source_aspect < target_aspect) {
        crop_height = (int)((float)source_width / target_aspect);
        crop_y = (source_height - crop_height) / 2;
    }

    for (int y = 0; y < MODEL_INPUT_HEIGHT; ++y) {
        const int src_y = crop_y + (y * crop_height) / MODEL_INPUT_HEIGHT;
        for (int x = 0; x < MODEL_INPUT_WIDTH; ++x) {
            const int src_x = crop_x + (x * crop_width) / MODEL_INPUT_WIDTH;
            const size_t src_index = ((size_t)src_y * source_width + src_x) * MODEL_INPUT_CHANNELS;
            const size_t dst_index = ((size_t)y * MODEL_INPUT_WIDTH + x) * MODEL_INPUT_CHANNELS;
            output[dst_index + 0] = quantize_rgb_value(rgb[src_index + 0], input_scale, input_zero_point);
            output[dst_index + 1] = quantize_rgb_value(rgb[src_index + 1], input_scale, input_zero_point);
            output[dst_index + 2] = quantize_rgb_value(rgb[src_index + 2], input_scale, input_zero_point);
        }
    }

    free(rgb);
    ESP_LOGI(TAG, "JPEG decoded and resized to %dx%d int8 input", MODEL_INPUT_WIDTH, MODEL_INPUT_HEIGHT);
    return ESP_OK;
}
