import argparse
import os
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "data" / "models" / "trainer_smoke" / "model_int8.tflite"
MPL_CACHE = ROOT / "data" / ".cache" / "matplotlib"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
warnings.filterwarnings("ignore", message=".*tf.lite.Interpreter is deprecated.*", category=UserWarning)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a TFLite model before ESP32-S3 integration.")
    parser.add_argument("--model", default=DEFAULT_MODEL, type=Path)
    args = parser.parse_args()

    model_path = args.model if args.model.is_absolute() else ROOT / args.model
    if not model_path.exists():
        print(f"[NG] Model not found: {model_path}")
        print("     Train a model first, then pass --model data\\models\\<RUN_NAME>\\model_int8.tflite")
        return 1

    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"Model: {model_path}")
    print(f"File size: {model_path.stat().st_size} bytes")
    print("Input details:")
    for item in input_details:
        print(item)
    print("Output details:")
    for item in output_details:
        print(item)

    input_shape = list(input_details[0]["shape"])
    input_dtype = input_details[0]["dtype"]
    output_shape = list(output_details[0]["shape"])

    if input_shape == [1, 96, 96, 3]:
        print("[OK] Input shape is [1, 96, 96, 3]")
    else:
        print(f"[WARN] Input shape is {input_shape}, expected [1, 96, 96, 3]")

    print(f"[OK] Input dtype: {input_dtype}")
    if len(output_shape) == 2 and output_shape[0] == 1:
        print(f"[OK] Output shape: {output_shape}")
    else:
        print(f"[WARN] Output shape is {output_shape}, expected [1, class_count]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
