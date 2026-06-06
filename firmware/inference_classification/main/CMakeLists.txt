idf_component_register(
    SRCS "main.c" "camera_config.c" "image_preprocess.c" "classifier.c" "model_data.cc"
    INCLUDE_DIRS "."
    REQUIRES esp_psram esp32-camera
)
