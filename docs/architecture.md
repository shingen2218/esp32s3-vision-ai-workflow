# Architecture

## Overview

The MVP separates capture/inference from training.

- ESP32-S3 captures JPEG frames and uploads them to the PC server.
- The PC server stores images, labels, and metadata.
- Dataset export, training, quantization, and C array conversion run on the PC.
- The inference firmware embeds `model_data.cc` and runs classification on ESP32-S3.

## Components

```text
ESP32-S3 Camera -> HTTP POST -> FastAPI -> SQLite + data/raw
                                      -> Web UI label update
                                      -> data/exported dataset
                                      -> Keras training
                                      -> TFLite int8
                                      -> C array
                                      -> ESP-IDF inference firmware
```

## MVP Boundary

This version supports image classification only. Object detection, Label Studio integration, OTA, auth, and cloud sync are intentionally outside the MVP.
