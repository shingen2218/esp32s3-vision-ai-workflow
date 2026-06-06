# ESP32 Firmware Build

Use an ESP-IDF PowerShell so `idf.py`, `cmake`, `ninja`, and `IDF_PATH` are available.

Check the ESP-IDF version first:

```powershell
idf.py --version
echo $env:IDF_PATH
```

This project has been build-checked with ESP-IDF v5.4.4 for Seeed Studio XIAO ESP32S3 Sense.

## Preflight Check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_espidf_env.ps1
```

This checks:

- `idf.py`
- `cmake`
- `ninja`
- Python 3.12
- `IDF_PATH`
- firmware directories
- `model_data.cc` and `model_data.h`

## Build capture_upload

`capture_upload` captures JPEG images and uploads them to the PC server.

Copy local Wi-Fi/server settings first:

```powershell
copy firmware\capture_upload\main\app_config.example.h firmware\capture_upload\main\app_config.h
notepad firmware\capture_upload\main\app_config.h
```

`app_config.h` is ignored by Git so Wi-Fi passwords and local IP addresses are not committed.

```powershell
cd firmware\capture_upload
idf.py set-target esp32s3
idf.py build
```

## Build inference_classification

`inference_classification` embeds `model_data.cc` and is the starting point for ESP32-S3 on-device classification.

```powershell
cd firmware\inference_classification
idf.py set-target esp32s3
idf.py build
```

## Build Both

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1
```

Use `-Clean` only when you intentionally want `idf.py fullclean` before each build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1 -Clean
```

## XIAO ESP32S3 Sense Camera Notes

The firmware uses a XIAO ESP32S3 Sense camera pin header and does not reuse AI Thinker ESP32-CAM pins.

The current pin mapping is based on Seeed's XIAO ESP32S3 Sense camera slot documentation:

- XCLK: GPIO10
- PCLK: GPIO13
- VSYNC: GPIO38
- HREF: GPIO47
- SIOD/SDA: GPIO40
- SIOC/SCL: GPIO39
- D0-D7: GPIO15, GPIO17, GPIO18, GPIO16, GPIO14, GPIO12, GPIO11, GPIO48

The camera uses JPEG format and starts with QVGA. PSRAM is enabled in `sdkconfig.defaults`; if PSRAM initialization fails, the code falls back to one DRAM frame buffer.

Flashing real hardware is a separate step and is not required for the current PC-side verification.
