import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def load_labels(path: Path) -> list[str]:
    labels = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [label for label in labels if label]


def load_image_array(image_path: Path, image_size: int) -> np.ndarray:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (image_size, image_size), method=Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32)
    return np.expand_dims(array, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one image through a trained Keras classifier.")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--image-size", type=int, default=96)
    parser.add_argument("--quiet-tf-log", action="store_true", help="Suppress TensorFlow info logs.")
    args = parser.parse_args()

    if args.quiet_tf_log:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

    import tensorflow as tf

    labels = load_labels(args.labels)
    model = tf.keras.models.load_model(args.model)
    inputs = load_image_array(args.image, args.image_size)
    probabilities = model.predict(inputs, verbose=0)[0]

    results = [
        {"label": label, "probability": float(probabilities[index])}
        for index, label in enumerate(labels)
    ]
    results.sort(key=lambda item: item["probability"], reverse=True)

    print("prediction:")
    for item in results:
        print(f"  {item['label']}: {item['probability']:.4f}")
    print(f"result: {results[0]['label']}")
    print(json.dumps({"predictions": results, "result": results[0]["label"]}, indent=2))


if __name__ == "__main__":
    main()
