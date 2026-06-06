import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TFLITE_PATH = ROOT / "data" / "models" / "trainer_smoke" / "model_int8.tflite"
CC_PATH = ROOT / "firmware" / "inference_classification" / "main" / "model_data.cc"
HEADER_PATH = ROOT / "firmware" / "inference_classification" / "main" / "model_data.h"


def main() -> int:
    if not TFLITE_PATH.exists():
        print(f"[NG] model_int8.tflite not found: {TFLITE_PATH}")
        print("     Run first:")
        print("     python scripts\\smoke_test_trainer.py")
        return 1

    command = [
        sys.executable,
        "tools/convert_tflite_to_c_array.py",
        "--input",
        str(TFLITE_PATH),
        "--cc",
        str(CC_PATH),
        "--header",
        str(HEADER_PATH),
    ]
    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print("[NG] C array conversion failed.")
        return result.returncode

    missing = [path for path in [CC_PATH, HEADER_PATH] if not path.exists()]
    if missing:
        for path in missing:
            print(f"[NG] Missing output: {path}")
        return 1

    print(f"[OK] {CC_PATH.relative_to(ROOT)} size={CC_PATH.stat().st_size} bytes")
    print(f"[OK] {HEADER_PATH.relative_to(ROOT)} size={HEADER_PATH.stat().st_size} bytes")
    print("\nModel export smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
