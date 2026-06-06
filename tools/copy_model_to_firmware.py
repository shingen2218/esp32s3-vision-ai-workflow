import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy generated model_data files into the inference firmware.")
    parser.add_argument("--cc", default="data/models/latest/model_data.cc", type=Path)
    parser.add_argument("--header", default="data/models/latest/model_data.h", type=Path)
    parser.add_argument("--firmware-main", default="firmware/inference_classification/main", type=Path)
    args = parser.parse_args()

    args.firmware_main.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.cc, args.firmware_main / "model_data.cc")
    shutil.copy2(args.header, args.firmware_main / "model_data.h")
    print(f"copied model files to {args.firmware_main}")


if __name__ == "__main__":
    main()
