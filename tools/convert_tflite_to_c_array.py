import argparse
from pathlib import Path


def bytes_to_c_array(data: bytes, symbol: str, header_name: str) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset : offset + 12]
        lines.append("  " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    body = "\n".join(lines)
    return f'#include "{header_name}"\n\nconst unsigned char {symbol}[] = {{\n{body}\n}};\nconst unsigned int {symbol}_len = {len(data)};\n'


def header_text(symbol: str) -> str:
    guard = symbol.upper() + "_H"
    return (
        "#pragma once\n\n"
        "#ifdef __cplusplus\n"
        'extern "C" {\n'
        "#endif\n\n"
        f"extern const unsigned char {symbol}[];\n"
        f"extern const unsigned int {symbol}_len;\n\n"
        "#ifdef __cplusplus\n"
        "}\n"
        "#endif\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a .tflite file into C source and header files.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--cc", required=True, type=Path)
    parser.add_argument("--header", required=True, type=Path)
    parser.add_argument("--symbol", default="model_data")
    args = parser.parse_args()

    data = args.input.read_bytes()
    args.cc.parent.mkdir(parents=True, exist_ok=True)
    args.header.parent.mkdir(parents=True, exist_ok=True)
    args.cc.write_text(bytes_to_c_array(data, args.symbol, args.header.name), encoding="utf-8")
    args.header.write_text(header_text(args.symbol), encoding="utf-8")
    print(f"wrote {args.cc} and {args.header}")


if __name__ == "__main__":
    main()
