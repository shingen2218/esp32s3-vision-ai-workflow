#include "camera_config.h"

#include "esp_log.h"
#include "esp_psram.h"
#include "esp_heap_caps.h"
#include "xiao_esp32s3_sense_camera_pins.h"

static const char *TAG = "camera_config";

esp_err_t camera_init(void)
{
    camera_config_t config = {
        .pin_pwdn = XIAO_CAM_PIN_PWDN,
        .pin_reset = XIAO_CAM_PIN_RESET,
        .pin_xclk = XIAO_CAM_PIN_XCLK,
        .pin_sccb_sda = XIAO_CAM_PIN_SIOD,
        .pin_sccb_scl = XIAO_CAM_PIN_SIOC,
        .pin_d7 = XIAO_CAM_PIN_D7,
        .pin_d6 = XIAO_CAM_PIN_D6,
        .pin_d5 = XIAO_CAM_PIN_D5,
        .pin_d4 = XIAO_CAM_PIN_D4,
        .pin_d3 = XIAO_CAM_PIN_D3,
        .pin_d2 = XIAO_CAM_PIN_D2,
        .pin_d1 = XIAO_CAM_PIN_D1,
        .pin_d0 = XIAO_CAM_PIN_D0,
        .pin_vsync = XIAO_CAM_PIN_VSYNC,
        .pin_href = XIAO_CAM_PIN_HREF,
        .pin_pclk = XIAO_CAM_PIN_PCLK,
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_QVGA,
        .jpeg_quality = 12,
        .fb_count = 2,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_LATEST,
    };

    if (!esp_psram_is_initialized()) {
        ESP_LOGW(TAG, "PSRAM is not initialized; using one DRAM frame buffer");
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    } else {
        ESP_LOGI(TAG, "PSRAM initialized, free PSRAM=%u", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    }
    ESP_LOGI(TAG, "free heap=%u", heap_caps_get_free_size(MALLOC_CAP_8BIT));

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "camera init failed: %s", esp_err_to_name(err));
    } else {
        ESP_LOGI(TAG, "camera init OK");
    }
    return err;
}

camera_fb_t *camera_capture_jpeg(void)
{
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        ESP_LOGE(TAG, "capture failed");
        return NULL;
    }
    if (fb->format != PIXFORMAT_JPEG) {
        ESP_LOGW(TAG, "captured frame is not JPEG");
    }
    ESP_LOGI(TAG, "captured JPEG size: %u bytes", fb->len);
    return fb;
}
