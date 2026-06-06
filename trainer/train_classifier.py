import argparse
import json
import os
from pathlib import Path


def build_tiny_cnn(tf, input_shape: tuple[int, int, int], class_count: int):
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=input_shape),
            tf.keras.layers.Rescaling(1.0 / 255.0),
            tf.keras.layers.Conv2D(16, 3, activation="relu"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(32, 3, activation="relu"),
            tf.keras.layers.MaxPooling2D(),
            tf.keras.layers.Conv2D(64, 3, activation="relu"),
            tf.keras.layers.GlobalAveragePooling2D(),
            tf.keras.layers.Dense(class_count, activation="softmax"),
        ]
    )
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a tiny CNN classifier.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--out-dir", default="data/models/latest", type=Path)
    parser.add_argument("--quiet-tf-log", action="store_true", help="Suppress TensorFlow info logs.")
    args = parser.parse_args()

    if args.quiet_tf_log:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

    import tensorflow as tf

    info = json.loads((args.dataset / "dataset_info.json").read_text(encoding="utf-8"))
    classes = info["classes"]
    image_size = int(info["image_size"])
    args.out_dir.mkdir(parents=True, exist_ok=True)

    train_ds = tf.keras.utils.image_dataset_from_directory(
        args.dataset / "train",
        labels="inferred",
        label_mode="int",
        class_names=classes,
        image_size=(image_size, image_size),
        batch_size=args.batch_size,
    )
    val_path = args.dataset / "val"
    val_ds = None
    if val_path.exists() and any(val_path.glob("*/*")):
        val_ds = tf.keras.utils.image_dataset_from_directory(
            val_path,
            labels="inferred",
            label_mode="int",
            class_names=classes,
            image_size=(image_size, image_size),
            batch_size=args.batch_size,
        )

    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.cache().shuffle(256).prefetch(autotune)
    if val_ds is not None:
        val_ds = val_ds.cache().prefetch(autotune)

    model = build_tiny_cnn(tf, (image_size, image_size, 3), len(classes))
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, verbose=2)
    model.save(args.out_dir / "model.keras")
    (args.out_dir / "labels.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    print(f"saved model to {args.out_dir}")


if __name__ == "__main__":
    main()
