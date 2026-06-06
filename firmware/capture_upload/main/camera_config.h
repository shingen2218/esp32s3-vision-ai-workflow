#pragma once

#include "esp_camera.h"

esp_err_t camera_init(void);
camera_fb_t *camera_capture_jpeg(void);
