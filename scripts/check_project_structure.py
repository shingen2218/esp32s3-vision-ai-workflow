from pathlib import Path
import sys


REQUIRED_PATHS = [
    "README.md",
    "server",
    "server/requirements.txt",
    "server/app/main.py",
    "server/app/database.py",
    "server/app/routes",
    "web",
    "trainer",
    "trainer/requirements.txt",
    "tools",
    "data",
    "firmware/capture_upload",
    "firmware/inference_classification",
    "docs",
]


def main() -> int:
    root = Path.cwd()
    failed = False

    for relative_path in REQUIRED_PATHS:
        path = root / relative_path
        if path.exists():
            print(f"[OK] {relative_path}")
        else:
            print(f"[NG] {relative_path}")
            failed = True

    if failed:
        print("\nProject structure check failed.")
        return 1

    print("\nProject structure check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
