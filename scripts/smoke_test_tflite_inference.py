import os
import warnings
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "data" / "models" / "trainer_smoke" / "model_int8.tflite"
LABELS_PATH = ROOT / "data" / "models" / "trainer_smoke" / "labels.txt"
DATASET_ROOT = ROOT / "data" / "trainer_smoke"
MPL_CACHE = ROOT / "data" / ".cache" / "matplotlib"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
warnings.filterwarnings("ignore", message=".*tf.lite.Interpreter is deprecated.*", category=UserWarning)


def find_test_image() -> Path | None:
    for split in ["test", "val"]:
        root = DATASET_ROOT / split
        if root.exists():
            for path in sorted(root.glob("*/*.jpg")):
                return path
    return None


def prepare_input(image_path: Path, input_detail: dict) -> np.ndarray:
    shape = input_detail["shape"]
    height = int(shape[1])
    width = int(shape[2])
    dtype = input_detail["dtype"]
    quant_scale, quant_zero_point = input_detail["quantization"]

    with Image.open(image_path) as image:
        image = image.convert("RGB").resize((width, height), Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32)

    if dtype == np.float32:
        array = array / 255.0
        return np.expand_dims(array.astype(np.float32), axis=0)
    if dtype == np.uint8:
        return np.expand_dims(array.astype(np.uint8), axis=0)
    if dtype == np.int8:
        if quant_scale == 0:
            raise RuntimeError("input quantization scale is 0")
        quantized = np.round(array / quant_scale + quant_zero_point)
        quantized = np.clip(quantized, -128, 127).astype(np.int8)
        return np.expand_dims(quantized, axis=0)

    raise RuntimeError(f"unsupported input dtype: {dtype}")


def dequantize_output(output: np.ndarray, output_detail: dict) -> np.ndarray:
    dtype = output_detail["dtype"]
    quant_scale, quant_zero_point = output_detail["quantization"]
    if dtype in (np.int8, np.uint8) and quant_scale != 0:
        return (output.astype(np.float32) - quant_zero_point) * quant_scale
    return output.astype(np.float32)


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"[NG] model_int8.tflite not found: {MODEL_PATH}")
        print("     Run: python scripts\\smoke_test_trainer.py")
        return 1
    if not LABELS_PATH.exists():
        print(f"[NG] labels.txt not found: {LABELS_PATH}")
        print("     Run: python scripts\\smoke_test_trainer.py")
        return 1

    import tensorflow as tf

    labels = [line.strip() for line in LABELS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    interpreter = tf.lite.Interpreter(model_path=str(MODEL_PATH))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    input_detail = input_details[0]
    output_detail = output_details[0]

    print("Input details:")
    print(input_detail)
    print("Output details:")
    print(output_detail)
    print(f"Input dtype: {input_detail['dtype']}")
    print(f"Input quantization: scale={input_detail['quantization'][0]} zero_point={input_detail['quantization'][1]}")

    image_path = find_test_image()
    if image_path is None:
        print(f"[NG] No test or val images found under {DATASET_ROOT}")
        print("     Run: python scripts\\smoke_test_trainer.py")
        return 1

    input_tensor = prepare_input(image_path, input_detail)
    interpreter.set_tensor(input_detail["index"], input_tensor)
    interpreter.invoke()
    output = interpreter.get_tensor(output_detail["index"])[0]
    scores = dequantize_output(output, output_detail)

    print(f"Image: {image_path.relative_to(ROOT)}")
    for index, score in enumerate(scores):
        label = labels[index] if index < len(labels) else f"class_{index}"
        print(f"{label}: {float(score):.4f}")

    best_index = int(np.argmax(scores))
    best_label = labels[best_index] if best_index < len(labels) else f"class_{best_index}"
    print(f"prediction: {best_label}")
    print("\nTFLite inference smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
