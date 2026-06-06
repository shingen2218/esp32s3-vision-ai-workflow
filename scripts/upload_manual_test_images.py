import argparse
from pathlib import Path
import sys

import requests


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "manual_test_images"
DEVICE_ID = "manual_test_pc"


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload manual test JPEGs to a running FastAPI server.")
    parser.add_argument("--server", default="http://localhost:8000", help="Base server URL, for example http://localhost:8000")
    args = parser.parse_args()

    if not IMAGE_DIR.exists():
        print(f"[NG] Test image directory does not exist: {IMAGE_DIR}")
        print("     Run: python scripts\\create_manual_test_images.py")
        return 1

    image_paths = sorted(IMAGE_DIR.glob("*.jpg"))
    if not image_paths:
        print(f"[NG] No JPEG files found in {IMAGE_DIR}")
        print("     Run: python scripts\\create_manual_test_images.py")
        return 1

    server = args.server.rstrip("/")
    upload_url = server + "/api/images/upload"
    try:
        health = requests.get(server + "/docs", timeout=5)
        health.raise_for_status()
    except requests.RequestException as exc:
        print(f"[NG] Server is not reachable: {args.server}")
        print("     Start it with: python -m uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000")
        print(f"     Detail: {exc}")
        return 1

    ok_count = 0
    for path in image_paths:
        try:
            with path.open("rb") as image_file:
                response = requests.post(
                    upload_url,
                    data={"device_id": DEVICE_ID},
                    files={"image": (path.name, image_file, "image/jpeg")},
                    timeout=15,
                )
            response.raise_for_status()
            data = response.json()
            ok_count += 1
            print(f"[OK] image_id={data.get('image_id')} filename={data.get('filename')} source={path.name}")
        except requests.RequestException as exc:
            print(f"[NG] Upload failed for {path.name}")
            print(f"     Detail: {exc}")
            return 1

    print(f"\nUploaded {ok_count} images to {upload_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
