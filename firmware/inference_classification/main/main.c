#include "classifier.h"
#include "image_preprocess.h"

#include "esp_camera.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

esp_err_t camera_init(void);

static const char *TAG = "inference";
static const char *LABELS[CLASS_COUNT] = {"target", "other"};

void app_main(void)
{
    ESP_ERROR_CHECK(camera_init());
    ESP_ERROR_CHECK(classifier_init());

    static int8_t input[MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS];

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "capture failed");
            vTaskDelay(pdMS_TO_TICKS(2000));
            continue;
        }

        classification_result_t result = {0};
        if (preprocess_jpeg_to_int8(fb->buf, fb->len, input, sizeof(input)) == ESP_OK &&
            classifier_run(input, &result) == ESP_OK) {
            ESP_LOGI(TAG, "prediction:");
            for (int i = 0; i < CLASS_COUNT; ++i) {
                ESP_LOGI(TAG, "  %s: %.2f", LABELS[i], result.scores[i]);
            }
            ESP_LOGI(TAG, "result: %s", LABELS[result.best_index]);
        }
        esp_camera_fb_return(fb);
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}
