import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.config import RAW_IMAGE_DIR
from server.app.database import get_db
from server.app.label_store import parse_labels


def load_labels(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_image_array(path: Path, image_size: int) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (image_size, image_size), method=Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32)
    return np.expand_dims(array, axis=0)


def read_reserved_images(limit: int):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, label
            FROM images
            WHERE COALESCE(reserved_for_test, 0) = 1
              AND status = 'labeled'
              AND label != 'unknown'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trained classifier on images reserved for human test review.")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--quiet-tf-log", action="store_true")
    args = parser.parse_args()

    if args.quiet_tf_log:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

    import tensorflow as tf

    labels_path = args.model_dir / "labels.txt"
    model_path = args.model_dir / "model.keras"
    labels = load_labels(labels_path)
    model = tf.keras.models.load_model(model_path)
    image_size = int(model.input_shape[1] or 96)

    results = []
    for row in read_reserved_images(args.limit):
        true_labels = [label for label in parse_labels(row["label"]) if label != "unknown"]
        if not true_labels:
            continue
        image_path = RAW_IMAGE_DIR / row["filename"]
        if not image_path.exists():
            results.append(
                {
                    "image_id": row["id"],
                    "filename": row["filename"],
                    "true_label": true_labels[0],
                    "error": "image file not found",
                }
            )
            continue
        probabilities = model.predict(load_image_array(image_path, image_size), verbose=0)[0]
        predictions = [
            {"label": label, "probability": float(probabilities[index])}
            for index, label in enumerate(labels)
        ]
        predictions.sort(key=lambda item: item["probability"], reverse=True)
        predicted_label = predictions[0]["label"]
        results.append(
            {
                "image_id": row["id"],
                "filename": row["filename"],
                "true_label": true_labels[0],
                "predicted_label": predicted_label,
                "correct": predicted_label == true_labels[0],
                "predictions": predictions,
            }
        )

    checked = [item for item in results if "correct" in item]
    correct_count = sum(1 for item in checked if item["correct"])
    output = {
        "ok": True,
        "model_dir": str(args.model_dir),
        "reserved_count": len(results),
        "checked_count": len(checked),
        "correct_count": correct_count,
        "accuracy": (correct_count / len(checked)) if checked else None,
        "results": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
