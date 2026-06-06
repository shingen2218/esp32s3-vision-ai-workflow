#include "http_upload.h"

#include <stdio.h>
#include <string.h>

#include "esp_http_client.h"
#include "esp_log.h"

static const char *TAG = "http_upload";

esp_err_t upload_jpeg(const char *server_url, const char *device_id, const uint8_t *jpeg, size_t jpeg_len)
{
    ESP_LOGI(TAG, "uploading JPEG: %u bytes device_id=%s url=%s", jpeg_len, device_id, server_url);
    const char *boundary = "----esp32s3vision";
    char head[512];
    int head_len = snprintf(
        head,
        sizeof(head),
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"device_id\"\r\n\r\n"
        "%s\r\n"
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n",
        boundary,
        device_id,
        boundary);
    char tail[64];
    int tail_len = snprintf(tail, sizeof(tail), "\r\n--%s--\r\n", boundary);

    esp_http_client_config_t config = {
        .url = server_url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 10000,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    char content_type[80];
    snprintf(content_type, sizeof(content_type), "multipart/form-data; boundary=%s", boundary);
    esp_http_client_set_header(client, "Content-Type", content_type);
    esp_err_t err = esp_http_client_open(client, head_len + jpeg_len + tail_len);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "http open failed: %s", esp_err_to_name(err));
        esp_http_client_cleanup(client);
        return err;
    }
    esp_http_client_write(client, head, head_len);
    esp_http_client_write(client, (const char *)jpeg, jpeg_len);
    esp_http_client_write(client, tail, tail_len);
    int content_length = esp_http_client_fetch_headers(client);
    int status = esp_http_client_get_status_code(client);
    char response[256] = {0};
    int read_len = esp_http_client_read_response(client, response, sizeof(response) - 1);
    if (read_len >= 0) {
        response[read_len] = '\0';
        ESP_LOGI(TAG, "server response: %s", response);
    } else {
        ESP_LOGW(TAG, "failed to read response body: %d", read_len);
    }
    ESP_LOGI(TAG, "upload status=%d content_length=%d", status, content_length);
    esp_http_client_cleanup(client);
    return status >= 200 && status < 300 ? ESP_OK : ESP_FAIL;
}
