idf_component_register(
    SRCS "main.c" "camera_config.c" "image_preprocess.c" "classifier.cc"
    INCLUDE_DIRS "."
    REQUIRES esp_psram esp32-camera esp_jpeg esp-tflite-micro esp_partition
)
