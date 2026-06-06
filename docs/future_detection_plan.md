# Future Detection Plan

Phase 2 adds object detection after the classification MVP is stable.

Planned scope:

- Label Studio integration
- Bounding-box annotation
- YOLO-format export
- Small detection model training
- ESP-DL or ESP-Detection export path
- Input size around 160x160 or 224x224
- 1 to 5 classes for embedded feasibility

Initial directory:

```text
detector/
├─ labelstudio_config/
├─ export_yolo.py
├─ train_detection.py
└─ espdl_export/
```

Detection is intentionally not implemented in the MVP.
