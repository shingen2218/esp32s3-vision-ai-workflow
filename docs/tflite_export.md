# TFLite Export

The trainer produces these model files:

- `model.keras`: Keras training output
- `model_float32.tflite`: float32 TensorFlow Lite model
- `model_int8.tflite`: int8 quantized TensorFlow Lite model
- `labels.txt`: class labels, one per line

## int8 Quantization

int8 quantization reduces model size and changes tensor values from floating point to integer values. This is useful for ESP32-S3 because memory and CPU resources are limited.

## representative_dataset

The TFLite converter needs representative images to estimate activation ranges for int8 quantization. `trainer/export_tflite.py` reads images from `train` and `val`, converts them to 96x96 RGB, and provides them as float32 arrays matching the model input range.

TensorFlow 2.21 can still print this warning during full-int8 export:

```text
Statistics for quantized inputs were expected, but not specified; continuing anyway.
```

In this project the representative dataset is supplied. If the final model input is int8 and `fully_quantize` is reported, use `scripts/inspect_tflite_model.py` to confirm the actual input/output tensors.

The generated int8 model explicitly requests:

```python
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8
```

## Inspect and Test

```powershell
python scripts\inspect_tflite_model.py --model data\models\<TRAIN_RUN_DIR>\model_int8.tflite
```

## Convert to C Array

ESP32-S3 firmware embeds the model through C source files:

```powershell
python tools\copy_model_to_firmware.py --model-dir data\models\<TRAIN_RUN_DIR>
```

This writes:

```text
firmware/inference_classification/main/model_data.cc
firmware/inference_classification/main/model_data.h
```

The ESP32-S3 inference firmware includes `model_data.cc`.
