# ESP32-S3 Setup

## Requirements

- ESP-IDF installed and activated
- ESP32-S3 camera board
- USB data cable
- `esp32-camera` managed component
- For inference, `esp-tflite-micro` or a compatible TensorFlow Lite Micro component

This project has been build-checked with ESP-IDF v5.4.4 and Seeed Studio XIAO ESP32S3 Sense.

## Capture Upload Firmware

`capture_upload` is the first real-device firmware to test. It connects Wi-Fi, initializes the camera, captures QVGA JPEG frames, and uploads them to the PC FastAPI server.

Open the local configuration file:

```powershell
notepad firmware\capture_upload\main\app_config.h
```

Set these values in `app_config.h`:

```c
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_UPLOAD_URL "http://YOUR_PC_IP:8000/api/images/upload"
#define DEVICE_ID "xiao_esp32s3_sense_001"
#define CAPTURE_TRIGGER_GPIO 0
#define CAPTURE_DEBOUNCE_MS 300
```

Do not paste Wi-Fi passwords into issues, logs, or documentation.

Find a likely PC LAN IP:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\get_pc_ip_hint.ps1
```

Start the PC server before flashing:

```powershell
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

Confirm these open in a browser:

```text
http://localhost:8000
http://localhost:8000/docs
```

List serial ports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\list_serial_ports.ps1
```

Flash and monitor from ESP-IDF PowerShell:

```powershell
cd firmware\capture_upload
idf.py -p COMx flash monitor
```

Replace `COMx` with the detected port.

Expected monitor logs:

```text
wifi connected
got ip: ...
camera init ok
ready: press BOOT/GPIO0 to capture and upload
capture button pressed
captured jpeg size=... bytes
upload status=200
server response: {"ok":true,...}
```

`capture_upload` waits after boot and captures one image when the BOOT button is pressed. Press BOOT again for the next image. Do not hold BOOT while resetting unless you intentionally want the ROM download mode.

If no COM port appears, try a known data-capable USB cable, reconnect while holding BOOT, press Reset, and check Windows Device Manager. If upload fails with connection errors, confirm the PC and ESP32-S3 are on the same LAN, the server URL uses the PC LAN IP, and Windows Firewall allows port 8000 on the private network.

## Inference Firmware

Generate `model_data.cc` and `model_data.h`, then build:

```powershell
python tools\copy_model_to_firmware.py --model-dir data\models\<TRAIN_RUN_DIR>
cd firmware\inference_classification
idf.py set-target esp32s3
idf.py build
```

Flash inference firmware only after `capture_upload` can reliably initialize the camera and upload images.

## Camera Notes

The current camera pin mapping targets Seeed Studio XIAO ESP32S3 Sense. Other ESP32-S3 camera boards need `camera_config.c` pin changes.
