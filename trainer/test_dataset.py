import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png"}


def load_labels(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_image_array(path: Path, image_size: int) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (image_size, image_size), method=Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32)
    return np.expand_dims(array, axis=0)


def iter_review_test_images(dataset_path: Path, limit: int):
    count = 0
    review_dir = dataset_path / "review_test"
    if not review_dir.exists():
        return
    for image_path in sorted(review_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        yield image_path
        count += 1
        if count >= limit:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained classifier on a dataset test split.")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--quiet-tf-log", action="store_true")
    args = parser.parse_args()

    if args.quiet_tf_log:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

    import tensorflow as tf

    info = json.loads((args.dataset / "dataset_info.json").read_text(encoding="utf-8"))
    image_size = int(info["image_size"])
    labels = load_labels(args.model_dir / "labels.txt")
    model = tf.keras.models.load_model(args.model_dir / "model.keras")

    results = []
    for image_path in iter_review_test_images(args.dataset, args.limit):
        probabilities = model.predict(load_image_array(image_path, image_size), verbose=0)[0]
        predictions = [
            {"label": label, "probability": float(probabilities[index])}
            for index, label in enumerate(labels)
        ]
        predictions.sort(key=lambda item: item["probability"], reverse=True)
        predicted_label = predictions[0]["label"]
        results.append(
            {
                "filename": image_path.name,
                "predicted_label": predicted_label,
                "predictions": predictions,
            }
        )

    output = {
        "ok": True,
        "dataset": str(args.dataset),
        "model_dir": str(args.model_dir),
        "checked_count": len(results),
        "review_mode": "human",
        "correct_count": None,
        "accuracy": None,
        "results": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
