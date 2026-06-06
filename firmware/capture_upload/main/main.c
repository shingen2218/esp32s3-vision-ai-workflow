#include "camera_config.h"
#include "http_upload.h"
#include "wifi_client.h"

#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "freertos/FreeRTOS.h"
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

static void capture_and_upload_once(void)
{
    camera_fb_t *fb = camera_capture_jpeg();
    if (!fb) {
        ESP_LOGE(TAG, "capture failed");
        return;
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
    configure_capture_button();
    ESP_LOGI(TAG, "camera init ok");
    ESP_LOGI(TAG, "ready: press BOOT/GPIO%d to capture and upload", CAPTURE_TRIGGER_GPIO);

    while (true) {
        wait_for_capture_button_press();
        ESP_LOGI(TAG, "capture button pressed");
        capture_and_upload_once();
        ESP_LOGI(TAG, "ready: press BOOT/GPIO%d to capture and upload", CAPTURE_TRIGGER_GPIO);
    }
}
