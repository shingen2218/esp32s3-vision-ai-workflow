cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS
    "managed_components/espressif__esp_jpeg"
    "../inference_classification/managed_components/espressif__esp32-camera"
    "../inference_classification/managed_components/espressif__esp-tflite-micro"
    "../inference_classification/managed_components/espressif__esp-nn"
)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(capture_upload)
