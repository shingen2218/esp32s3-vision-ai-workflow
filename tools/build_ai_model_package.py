import argparse
import binascii
import struct
from pathlib import Path


MAGIC = b"AIMDL001"
VERSION = 1
HEADER_FORMAT = "<8sIIIIIII"
HEADER_SIZE = 4096


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def build_package(model_path: Path, labels_path: Path, output_path: Path) -> dict:
    model_data = model_path.read_bytes()
    labels_text = labels_path.read_text(encoding="utf-8")
    labels = [line.strip() for line in labels_text.splitlines() if line.strip()]
    if not labels:
        raise ValueError(f"labels.txt has no labels: {labels_path}")
    labels_data = ("\n".join(labels) + "\n").encode("utf-8")

    model_offset = HEADER_SIZE
    labels_offset = align(model_offset + len(model_data), 16)
    package_size = labels_offset + len(labels_data)
    package = bytearray(package_size)
    package[model_offset : model_offset + len(model_data)] = model_data
    package[labels_offset : labels_offset + len(labels_data)] = labels_data

    crc = binascii.crc32(package[model_offset:]) & 0xFFFFFFFF
    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        model_offset,
        len(model_data),
        labels_offset,
        len(labels_data),
        crc,
    )
    package[: len(header)] = header

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(package)
    return {
        "output": str(output_path),
        "package_size": len(package),
        "model_size": len(model_data),
        "labels_size": len(labels_data),
        "label_count": len(labels),
        "crc32": f"0x{crc:08x}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an ai_model.bin package for the ESP32-S3 model partition.")
    parser.add_argument("--model", required=True, type=Path, help="Path to model_int8.tflite")
    parser.add_argument("--labels", required=True, type=Path, help="Path to labels.txt")
    parser.add_argument("--output", required=True, type=Path, help="Output ai_model.bin path")
    args = parser.parse_args()

    info = build_package(args.model, args.labels, args.output)
    for key, value in info.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
