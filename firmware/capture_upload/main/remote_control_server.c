#include "remote_control_server.h"

#include <stdio.h>

#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "remote_control";
static const char *STREAM_BOUNDARY = "123456789000000000000987654321";
static const int REMOTE_CONTROL_PORT = 8080;

typedef struct {
    remote_capture_callback_t capture_callback;
    remote_infer_callback_t infer_callback;
    void *capture_context;
} remote_control_context_t;

static remote_control_context_t server_context = {0};

static void set_cors_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type");
}

static esp_err_t root_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "text/plain");
    return httpd_resp_sendstr(req, "ESP32-S3 camera is ready. Use /stream, /capture, or /infer.");
}

static esp_err_t capture_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    if (!server_context.capture_callback) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"error\":\"capture callback not configured\"}");
    }

    ESP_LOGI(TAG, "remote capture requested");
    esp_err_t err = server_context.capture_callback(server_context.capture_context);
    httpd_resp_set_type(req, "application/json");
    if (err != ESP_OK) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"error\":\"capture upload failed\"}");
    }
    return httpd_resp_sendstr(req, "{\"ok\":true,\"message\":\"capture uploaded\"}");
}

static esp_err_t infer_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");
    if (!server_context.infer_callback) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"error\":\"inference callback not configured\"}");
    }

    char response[768];
    esp_err_t err = server_context.infer_callback(response, sizeof(response), server_context.capture_context);
    if (err != ESP_OK) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"error\":\"inference failed\"}");
    }
    return httpd_resp_sendstr(req, response);
}

static esp_err_t stream_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=123456789000000000000987654321");

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "stream capture failed");
            return ESP_FAIL;
        }

        char header[128];
        int header_len = snprintf(
            header,
            sizeof(header),
            "\r\n--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
            STREAM_BOUNDARY,
            (unsigned int)fb->len);

        esp_err_t err = httpd_resp_send_chunk(req, header, header_len);
        if (err == ESP_OK) {
            err = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
        }
        esp_camera_fb_return(fb);

        if (err != ESP_OK) {
            ESP_LOGI(TAG, "stream client disconnected");
            return err;
        }
        vTaskDelay(pdMS_TO_TICKS(120));
    }
}

esp_err_t remote_control_server_start(
    remote_capture_callback_t capture_callback,
    remote_infer_callback_t infer_callback,
    void *context)
{
    server_context.capture_callback = capture_callback;
    server_context.infer_callback = infer_callback;
    server_context.capture_context = context;

    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = REMOTE_CONTROL_PORT;
    config.ctrl_port = 32768;
    config.stack_size = 8192;

    httpd_handle_t server = NULL;
    esp_err_t err = httpd_start(&server, &config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "failed to start HTTP server: %s", esp_err_to_name(err));
        return err;
    }

    const httpd_uri_t root_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = root_handler,
        .user_ctx = NULL,
    };
    const httpd_uri_t capture_uri = {
        .uri = "/capture",
        .method = HTTP_GET,
        .handler = capture_handler,
        .user_ctx = NULL,
    };
    const httpd_uri_t stream_uri = {
        .uri = "/stream",
        .method = HTTP_GET,
        .handler = stream_handler,
        .user_ctx = NULL,
    };
    const httpd_uri_t infer_uri = {
        .uri = "/infer",
        .method = HTTP_GET,
        .handler = infer_handler,
        .user_ctx = NULL,
    };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &root_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &capture_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &stream_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &infer_uri));

    ESP_LOGI(TAG, "remote control server started on port %d: /stream /capture /infer", REMOTE_CONTROL_PORT);
    return ESP_OK;
}
