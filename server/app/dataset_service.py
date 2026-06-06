import json
import random
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from .config import EXPORTED_DIR, RAW_IMAGE_DIR
from .database import get_db
from .label_store import parse_labels


def export_classification_dataset(
    dataset_name: str,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    image_size: int,
    seed: int = 42,
) -> Path:
    total = train_ratio + val_ratio + test_ratio
    if total <= 0:
        raise ValueError("split ratios must be positive")

    output_dir = EXPORTED_DIR / dataset_name
    if output_dir.exists():
        shutil.rmtree(output_dir)

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, label, COALESCE(reserved_for_test, 0) AS reserved_for_test
            FROM images
            WHERE status = 'labeled'
              AND label != 'unknown'
            """
        ).fetchall()
        unknown_count = conn.execute(
            "SELECT COUNT(*) FROM images WHERE status = 'unlabeled' OR label = 'unknown'"
        ).fetchone()[0]
        reserved_test_count = conn.execute(
            "SELECT COUNT(*) FROM images WHERE COALESCE(reserved_for_test, 0) = 1"
        ).fetchone()[0]

    rows_with_label = []
    rows_for_review_test = []
    class_names: set[str] = set()
    for row in rows:
        raw_labels = parse_labels(row["label"])
        if "test" in raw_labels:
            rows_for_review_test.append(row)
            continue
        labels = [label for label in raw_labels if label != "unknown"]
        if not labels:
            continue
        # Classification is one label per image. If older data has multiple
        # labels, use the first label so the export remains deterministic.
        class_name = labels[0]
        rows_with_label.append((row, class_name))
        class_names.add(class_name)

    if not rows_with_label and not rows_for_review_test:
        raise ValueError("no labeled images found. Add one label to each image before exporting a dataset.")
    if not rows_with_label:
        raise ValueError("no training images found. Add normal labeled images in addition to test images.")

    classes = sorted(class_names)
    for split in ["train", "val", "test"]:
        for label in classes:
            (output_dir / split / label).mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list] = {label: [] for label in classes}
    for row, class_name in rows_with_label:
        grouped[class_name].append(row)
    rng = random.Random(seed)
    counts = {"train": 0, "val": 0, "test": 0, "review_test": 0}
    train_val_total = train_ratio + val_ratio
    normalized_train = train_ratio / train_val_total if train_val_total > 0 else 1.0

    for label, items in grouped.items():
        rng.shuffle(items)
        train_end = int(len(items) * normalized_train)
        if items and train_end == 0:
            train_end = 1
        splits = {
            "train": items[:train_end],
            "val": items[train_end:],
        }
        for split, split_rows in splits.items():
            for row in split_rows:
                source = RAW_IMAGE_DIR / row["filename"]
                target = output_dir / split / label / row["filename"]
                resize_for_training(source, target, image_size)
                counts[split] += 1

    review_test_dir = output_dir / "review_test"
    review_test_dir.mkdir(parents=True, exist_ok=True)
    for row in rows_for_review_test:
        source = RAW_IMAGE_DIR / row["filename"]
        target = review_test_dir / row["filename"]
        resize_for_training(source, target, image_size)
        counts["review_test"] += 1

    info = {
        "name": dataset_name,
        "dataset_type": "classification",
        "classes": classes,
        "image_size": image_size,
        "train_count": counts["train"],
        "val_count": counts["val"],
        "test_count": counts["test"],
        "review_test_count": counts["review_test"],
        "label_counts": {label: len(items) for label, items in grouped.items()},
        "test_label": "test",
        "excluded_unknown_count": unknown_count,
        "excluded_reserved_test_count": reserved_test_count,
    }
    (output_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return output_dir


def resize_for_training(source: Path, target: Path, image_size: int) -> None:
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = ImageOps.fit(img, (image_size, image_size), method=Image.Resampling.BILINEAR)
        img.save(target, format="JPEG", quality=92)
