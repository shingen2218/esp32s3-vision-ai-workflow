idf_component_register(
    SRCS
        "main.c"
        "camera_config.c"
        "wifi_client.c"
        "http_upload.c"
        "remote_control_server.c"
        "../../inference_classification/main/classifier.cc"
        "../../inference_classification/main/image_preprocess.c"
    INCLUDE_DIRS "." "../../inference_classification/main"
    REQUIRES esp_http_client esp_http_server esp_wifi nvs_flash esp_event esp_netif esp_psram esp_driver_gpio esp32-camera esp_jpeg esp-tflite-micro esp_partition
)
