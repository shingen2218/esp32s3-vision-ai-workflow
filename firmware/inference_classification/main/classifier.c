#include "classifier.h"

#include "esp_log.h"
#include "model_data.h"

static const char *TAG = "classifier";

esp_err_t classifier_init(void)
{
    ESP_LOGI(TAG, "model bytes: %u", model_data_len);
    // Placeholder: initialize TensorFlow Lite Micro interpreter here.
    return ESP_OK;
}

esp_err_t classifier_run(const int8_t *input, classification_result_t *result)
{
    (void)input;
    // Placeholder result until TFLite Micro is wired in for the target board.
    result->scores[0] = 0.5f;
    result->scores[1] = 0.5f;
    result->best_index = 0;
    return ESP_OK;
}
