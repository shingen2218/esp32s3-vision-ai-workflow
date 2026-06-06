idf_component_register(
    SRCS "main.c" "camera_config.c" "wifi_client.c" "http_upload.c"
    INCLUDE_DIRS "."
    REQUIRES esp_http_client esp_wifi nvs_flash esp_event esp_netif esp_psram esp_driver_gpio esp32-camera
)
