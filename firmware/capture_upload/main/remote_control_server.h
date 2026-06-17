#pragma once

#include <stddef.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef esp_err_t (*remote_capture_callback_t)(void *context);
typedef esp_err_t (*remote_infer_callback_t)(char *buffer, size_t buffer_len, void *context);

esp_err_t remote_control_server_start(
    remote_capture_callback_t capture_callback,
    remote_infer_callback_t infer_callback,
    void *context);

#ifdef __cplusplus
}
#endif
