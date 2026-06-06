#include "esp_camera.h"
#include "esp_err.h"
#include "esp_psram.h"
#include "xiao_esp32s3_sense_camera_pins.h"

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
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    }
    return esp_camera_init(&config);
}
