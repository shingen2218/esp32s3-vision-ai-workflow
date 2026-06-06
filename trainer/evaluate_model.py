import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained Keras classifier.")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    info = json.loads((args.dataset / "dataset_info.json").read_text(encoding="utf-8"))
    classes = info["classes"]
    image_size = int(info["image_size"])
    ds = tf.keras.utils.image_dataset_from_directory(
        args.dataset / args.split,
        labels="inferred",
        label_mode="int",
        class_names=classes,
        image_size=(image_size, image_size),
        batch_size=16,
        shuffle=False,
    )
    model = tf.keras.models.load_model(args.model)
    y_true = np.concatenate([labels.numpy() for _, labels in ds])
    y_prob = model.predict(ds)
    y_pred = np.argmax(y_prob, axis=1)
    print("confusion matrix")
    print(confusion_matrix(y_true, y_pred))
    print(classification_report(y_true, y_pred, target_names=classes))


if __name__ == "__main__":
    main()
