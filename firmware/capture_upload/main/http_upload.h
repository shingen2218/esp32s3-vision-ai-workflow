#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

esp_err_t upload_jpeg(const char *server_url, const char *device_id, const uint8_t *jpeg, size_t jpeg_len);
