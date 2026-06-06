#pragma once

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_UPLOAD_URL "http://YOUR_PC_IP:8000/api/images/upload"
#define DEVICE_ID "xiao_esp32s3_sense_001"

// XIAO ESP32S3 Sense BOOT button is GPIO0. Press it after boot to capture one image.
#define CAPTURE_TRIGGER_GPIO 0
#define CAPTURE_DEBOUNCE_MS 300
