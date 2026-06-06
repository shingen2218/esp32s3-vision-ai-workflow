import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image


def iter_representative_images(dataset_path: Path, image_size: int, limit: int = 100):
    image_roots = [dataset_path / "train", dataset_path / "val"]
    image_paths = []
    for root in image_roots:
        if root.exists():
            image_paths.extend(sorted(root.glob("*/*.jpg")))
            image_paths.extend(sorted(root.glob("*/*.jpeg")))
            image_paths.extend(sorted(root.glob("*/*.png")))

    if not image_paths:
        raise RuntimeError(f"no representative images found under {dataset_path / 'train'} or {dataset_path / 'val'}")

    for path in image_paths[:limit]:
        with Image.open(path) as image:
            image = image.convert("RGB").resize((image_size, image_size), Image.Resampling.BILINEAR)
            array = np.asarray(image, dtype=np.float32)
            # The Keras model contains a Rescaling(1/255) layer, so representative data
            # should match the model's raw RGB input range.
            yield [np.expand_dims(array, axis=0)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Keras model to float32 and int8 TFLite.")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out-dir", default="data/models/latest", type=Path)
    parser.add_argument("--quiet-tf-log", action="store_true", help="Suppress TensorFlow info logs.")
    args = parser.parse_args()

    if args.quiet_tf_log:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

    import tensorflow as tf

    args.out_dir.mkdir(parents=True, exist_ok=True)
    info = json.loads((args.dataset / "dataset_info.json").read_text(encoding="utf-8"))
    image_size = int(info["image_size"])
    model = tf.keras.models.load_model(args.model)

    float_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    float_tflite = float_converter.convert()
    (args.out_dir / "model_float32.tflite").write_bytes(float_tflite)

    int8_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    int8_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    int8_converter.representative_dataset = lambda: iter_representative_images(args.dataset, image_size)
    int8_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    int8_converter.inference_input_type = tf.int8
    int8_converter.inference_output_type = tf.int8
    try:
        int8_tflite = int8_converter.convert()
    except Exception as exc:
        print("[NG] int8 TFLite conversion failed.")
        print("     The model may need float fallback or an op change.")
        print(f"     Detail: {exc}")
        raise
    (args.out_dir / "model_int8.tflite").write_bytes(int8_tflite)
    print(f"wrote TFLite files to {args.out_dir}")


if __name__ == "__main__":
    main()
