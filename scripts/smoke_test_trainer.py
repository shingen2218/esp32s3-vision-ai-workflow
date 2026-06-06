import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data" / "trainer_smoke"
MODEL_DIR = ROOT / "data" / "models" / "trainer_smoke"
CLASSES = ["target", "other"]
IMAGE_SIZE = 96
MPL_CACHE = ROOT / "data" / ".cache" / "matplotlib"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     Detail: {detail}")
    return 1


def print_python_info() -> None:
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    if sys.version_info[:2] != (3, 12):
        print("[WARN] This project expects Python 3.12.x for TensorFlow trainer checks.")


def load_font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 14)
    except OSError:
        return ImageFont.load_default()


def draw_label(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> None:
    draw.text((8, 74), text, fill=(20, 24, 32), font=font)


def make_image(label: str, index: int, path: Path, font: ImageFont.ImageFont) -> None:
    image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), color=(248, 250, 252))
    draw = ImageDraw.Draw(image)
    offset = index % 8
    if label == "target":
        draw.ellipse((22 + offset, 14, 74 + offset, 66), fill=(220, 38, 38), outline=(127, 29, 29), width=2)
    else:
        draw.rectangle((22 + offset, 14, 74 + offset, 66), fill=(37, 99, 235), outline=(30, 64, 175), width=2)
    draw_label(draw, f"{label}_{index:02d}", font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=92)


def create_dataset() -> None:
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)

    split_counts = {"train": 14, "val": 4, "test": 2}
    font = load_font()
    total_counts = {"train": 0, "val": 0, "test": 0}

    for label in CLASSES:
        image_index = 1
        for split, count in split_counts.items():
            for _ in range(count):
                path = DATASET_DIR / split / label / f"{label}_{image_index:03d}.jpg"
                make_image(label, image_index, path, font)
                total_counts[split] += 1
                image_index += 1

    info = {
        "name": "trainer_smoke",
        "classes": CLASSES,
        "image_size": IMAGE_SIZE,
        "train_count": total_counts["train"],
        "val_count": total_counts["val"],
        "test_count": total_counts["test"],
    }
    (DATASET_DIR / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    ok(f"Created trainer smoke dataset: {DATASET_DIR}")


def run_command(command: list[str]) -> int:
    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


def require_file(path: Path) -> bool:
    if path.exists():
        ok(f"Generated {path.relative_to(ROOT)}")
        return True
    print(f"[NG] Missing {path.relative_to(ROOT)}")
    return False


def main() -> int:
    print_python_info()

    try:
        import tensorflow as tf

        ok(f"TensorFlow import: {tf.__version__}")
    except Exception as exc:
        return fail(
            "TensorFlow import failed",
            f"{exc}\n     Run: python -m pip install -r trainer\\requirements.txt",
        )

    create_dataset()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    train_result = run_command(
        [
            sys.executable,
            "trainer/train_classifier.py",
            "--dataset",
            str(DATASET_DIR),
            "--epochs",
            "1",
            "--batch-size",
            "4",
            "--out-dir",
            str(MODEL_DIR),
            "--quiet-tf-log",
        ]
    )
    if train_result != 0:
        return fail("Training command failed")

    export_result = run_command(
        [
            sys.executable,
            "trainer/export_tflite.py",
            "--model",
            str(MODEL_DIR / "model.keras"),
            "--dataset",
            str(DATASET_DIR),
            "--out-dir",
            str(MODEL_DIR),
            "--quiet-tf-log",
        ]
    )
    if export_result != 0:
        return fail("TFLite export command failed")

    required_files = [
        MODEL_DIR / "model.keras",
        MODEL_DIR / "model_float32.tflite",
        MODEL_DIR / "model_int8.tflite",
        MODEL_DIR / "labels.txt",
    ]
    if not all(require_file(path) for path in required_files):
        return 1

    print("\nSmoke trainer test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
