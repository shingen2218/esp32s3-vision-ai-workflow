#include "image_preprocess.h"

#include "esp_log.h"

static const char *TAG = "image_preprocess";

esp_err_t preprocess_jpeg_to_int8(const uint8_t *jpeg, size_t jpeg_len, int8_t *output, size_t output_len)
{
    (void)jpeg;
    (void)jpeg_len;
    if (output_len < MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS) {
        return ESP_ERR_INVALID_SIZE;
    }

    // Placeholder: replace with JPEG decode, resize to 96x96 RGB, and quantize using model input params.
    for (size_t i = 0; i < MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS; ++i) {
        output[i] = 0;
    }
    ESP_LOGW(TAG, "preprocess placeholder produced zero input");
    return ESP_OK;
}
