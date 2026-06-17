#include "camera_config.h"
#include "classifier.h"
#include "http_upload.h"
#include "image_preprocess.h"
#include "remote_control_server.h"
#include "wifi_client.h"

#include "esp_camera.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "driver/gpio.h"

#if __has_include("app_config.h")
#include "app_config.h"
#else
#warning "Using app_config.example.h. Copy it to app_config.h and set Wi-Fi/server values before flashing."
#include "app_config.example.h"
#endif

#ifndef CAPTURE_TRIGGER_GPIO
#define CAPTURE_TRIGGER_GPIO 0
#endif

#ifndef CAPTURE_DEBOUNCE_MS
#define CAPTURE_DEBOUNCE_MS 300
#endif

static const char *TAG = "capture_upload";

typedef struct {
    const char *source;
    SemaphoreHandle_t done;
    esp_err_t *result;
} capture_request_t;

static QueueHandle_t capture_queue;
static int8_t inference_input[MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS];
static bool inference_ready = false;

static void configure_capture_button(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = 1ULL << CAPTURE_TRIGGER_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&io_conf));
}

static esp_err_t capture_and_upload_once(void)
{
    camera_fb_t *fb = camera_capture_jpeg();
    if (!fb) {
        ESP_LOGE(TAG, "capture failed");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "captured jpeg size=%u bytes", (unsigned int)fb->len);
    esp_err_t err = ESP_FAIL;
    for (int attempt = 1; attempt <= 3; ++attempt) {
        err = upload_jpeg(SERVER_UPLOAD_URL, DEVICE_ID, fb->buf, fb->len);
        ESP_LOGI(TAG, "upload attempt %d result: %s", attempt, esp_err_to_name(err));
        if (err == ESP_OK) {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    esp_camera_fb_return(fb);
    return err;
}

static esp_err_t submit_capture_request(const char *source, TickType_t wait_ticks)
{
    if (!capture_queue) {
        return ESP_ERR_INVALID_STATE;
    }
    capture_request_t request = {
        .source = source,
        .done = NULL,
        .result = NULL,
    };
    if (xQueueSend(capture_queue, &request, wait_ticks) != pdTRUE) {
        ESP_LOGW(TAG, "capture queue is full; source=%s", source);
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

static esp_err_t submit_capture_request_and_wait(const char *source, TickType_t wait_ticks)
{
    if (!capture_queue) {
        return ESP_ERR_INVALID_STATE;
    }

    SemaphoreHandle_t done = xSemaphoreCreateBinary();
    if (!done) {
        return ESP_ERR_NO_MEM;
    }

    esp_err_t result = ESP_FAIL;
    capture_request_t request = {
        .source = source,
        .done = done,
        .result = &result,
    };

    if (xQueueSend(capture_queue, &request, wait_ticks) != pdTRUE) {
        ESP_LOGW(TAG, "capture queue is full; source=%s", source);
        vSemaphoreDelete(done);
        return ESP_ERR_TIMEOUT;
    }

    if (xSemaphoreTake(done, wait_ticks) != pdTRUE) {
        ESP_LOGW(TAG, "capture request timed out; source=%s", source);
        vSemaphoreDelete(done);
        return ESP_ERR_TIMEOUT;
    }

    vSemaphoreDelete(done);
    return result;
}

static void capture_task(void *arg)
{
    (void)arg;
    capture_request_t request = {0};
    while (true) {
        if (xQueueReceive(capture_queue, &request, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        ESP_LOGI(TAG, "capture request started; source=%s", request.source);
        esp_err_t result = capture_and_upload_once();
        ESP_LOGI(TAG, "capture request finished; source=%s result=%s", request.source, esp_err_to_name(result));

        if (request.result) {
            *request.result = result;
        }
        if (request.done) {
            xSemaphoreGive(request.done);
        }
    }
}

static esp_err_t remote_capture_callback(void *context)
{
    (void)context;
    return submit_capture_request_and_wait("remote", pdMS_TO_TICKS(30000));
}

static esp_err_t remote_infer_callback(char *buffer, size_t buffer_len, void *context)
{
    (void)context;
    if (!buffer || buffer_len == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!inference_ready) {
        ESP_LOGW(TAG, "inference requested before model is ready");
        return ESP_ERR_INVALID_STATE;
    }

    camera_fb_t *fb = camera_capture_jpeg();
    if (!fb) {
        ESP_LOGE(TAG, "inference capture failed");
        return ESP_FAIL;
    }

    classification_result_t result = {0};
    esp_err_t err = preprocess_jpeg_to_int8(
        fb->buf,
        fb->len,
        inference_input,
        sizeof(inference_input),
        classifier_input_scale(),
        classifier_input_zero_point());
    if (err == ESP_OK) {
        err = classifier_run(inference_input, &result);
    }
    esp_camera_fb_return(fb);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "inference failed: %s", esp_err_to_name(err));
        return err;
    }

    int written = snprintf(
        buffer,
        buffer_len,
        "{\"ok\":true,\"best_index\":%d,\"label\":\"%s\",\"scores\":[",
        result.best_index,
        classifier_label(result.best_index));
    for (int i = 0; i < result.score_count && written > 0 && (size_t)written < buffer_len; ++i) {
        written += snprintf(
            buffer + written,
            buffer_len - written,
            "%s{\"label\":\"%s\",\"score\":%.6f}",
            i == 0 ? "" : ",",
            classifier_label(i),
            result.scores[i]);
    }
    if (written <= 0 || (size_t)written >= buffer_len) {
        return ESP_ERR_NO_MEM;
    }
    snprintf(buffer + written, buffer_len - written, "]}");
    ESP_LOGI(TAG, "inference result: %s", classifier_label(result.best_index));
    return ESP_OK;
}

static void wait_for_capture_button_press(void)
{
    while (gpio_get_level(CAPTURE_TRIGGER_GPIO) == 1) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    vTaskDelay(pdMS_TO_TICKS(CAPTURE_DEBOUNCE_MS));
    while (gpio_get_level(CAPTURE_TRIGGER_GPIO) == 0) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "device_id=%s", DEVICE_ID);
    ESP_LOGI(TAG, "server_upload_url=%s", SERVER_UPLOAD_URL);
    ESP_LOGI(TAG, "capture mode: press GPIO%d button to capture one image", CAPTURE_TRIGGER_GPIO);
    ESP_LOGI(TAG, "psram=%s free_heap=%lu free_psram=%lu",
             esp_psram_is_initialized() ? "initialized" : "not initialized",
             (unsigned long)esp_get_free_heap_size(),
             (unsigned long)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    ESP_ERROR_CHECK(wifi_connect_sta(WIFI_SSID, WIFI_PASSWORD));
    ESP_ERROR_CHECK(camera_init());
    esp_err_t classifier_err = classifier_init();
    if (classifier_err == ESP_OK) {
        inference_ready = true;
        ESP_LOGI(TAG, "inference init ok");
    } else {
        ESP_LOGW(TAG, "inference disabled until ai_model partition is written: %s", esp_err_to_name(classifier_err));
    }
    capture_queue = xQueueCreate(4, sizeof(capture_request_t));
    ESP_ERROR_CHECK(capture_queue ? ESP_OK : ESP_ERR_NO_MEM);
    BaseType_t task_created = xTaskCreate(capture_task, "capture_task", 8192, NULL, 5, NULL);
    ESP_ERROR_CHECK(task_created == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(remote_control_server_start(remote_capture_callback, remote_infer_callback, NULL));
    configure_capture_button();
    ESP_LOGI(TAG, "camera init ok");
    ESP_LOGI(TAG, "ready: open http://<esp32-ip>:8080/stream, /capture, or /infer");

    while (true) {
        wait_for_capture_button_press();
        ESP_LOGI(TAG, "capture button pressed");
        (void)submit_capture_request("button", pdMS_TO_TICKS(100));
        ESP_LOGI(TAG, "ready: press BOOT/GPIO%d to capture and upload", CAPTURE_TRIGGER_GPIO);
    }
}
