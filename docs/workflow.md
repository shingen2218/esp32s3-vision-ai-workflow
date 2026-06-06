# Workflow

1. Start the PC server.
2. Upload JPEG images from ESP32-S3 or curl.
3. Review captured images in the Web UI.
4. Click one image to inspect it.
5. Create free labels such as `screw`, `metal`, or `defect`.
6. Select several images that show the same target.
7. Apply one label to each image from the label palette.
8. Download the label CSV if needed.
9. Export a classification dataset.
10. Train the tiny CNN.
11. Export float32 and int8 TFLite models.
12. Convert `model_int8.tflite` to `model_data.cc` and `model_data.h`.
13. Build and flash the inference firmware.

## Web UI Labeling

- Click an image card to show the larger preview.
- Add a free label with `New label` and `Add Label`.
- Reuse existing labels from the label palette.
- Use the checkbox on each card to select multiple images.
- Click a label chip to set that label on the current image or checked images.
- Use `Bulk Label` to apply one label to all checked images.
- Use `Download label CSV` to export labeled rows.

CSV output:

```text
image_id,filename,label,screw,nut,metal,target,other,unknown
37,xiao_esp32s3_sense_001_000011.jpg,screw,1,0,0,0,0,0
```

This is multi-class image classification, not object detection. If the model must learn object positions, the Phase 2 workflow needs Bounding Box annotations.

## Commands

```bash
uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000
python tools/make_dataset.py --name dataset_v001 --image-size 96
python trainer/train_classifier.py --dataset data/exported/dataset_v001 --epochs 30
python trainer/export_tflite.py --model data/models/latest/model.keras --dataset data/exported/dataset_v001
python tools/convert_tflite_to_c_array.py --input data/models/latest/model_int8.tflite --cc firmware/inference_classification/main/model_data.cc --header firmware/inference_classification/main/model_data.h
python scripts\inspect_tflite_model.py --model data\models\latest\model_int8.tflite
powershell -ExecutionPolicy Bypass -File scripts\check_espidf_env.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1
```

## Before ESP32-S3 Hardware

- [ ] Python 3.12が使われている
- [ ] http://localhost:8000 が開く
- [ ] http://localhost:8000/docs が開く
- [ ] Web UIで画像にラベル付けできる
- [ ] dataset export ができる
- [ ] model_int8.tflite が生成される
- [ ] model_data.cc / model_data.h が生成される
- [ ] ESP-IDFが使える
- [ ] capture_upload firmware がbuildできる
- [ ] inference_classification firmware がbuildできる
