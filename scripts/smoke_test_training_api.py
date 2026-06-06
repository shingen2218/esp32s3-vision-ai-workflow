from io import BytesIO
from pathlib import Path
import shutil
import sys
import time

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.main import app


DATASET_NAME = "training_api_smoke_dataset"
DATASET_PATH = ROOT / "data" / "exported" / DATASET_NAME


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def make_jpeg(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    image = Image.new("RGB", (96, 96), color=color)
    image.save(buffer, format="JPEG", quality=90)
    path.write_bytes(buffer.getvalue())


def create_training_dataset() -> None:
    if DATASET_PATH.exists():
        shutil.rmtree(DATASET_PATH)
    classes = ["target", "other"]
    for index in range(4):
        make_jpeg(DATASET_PATH / "train" / "target" / f"target_{index}.jpg", (220, 40, 40))
        make_jpeg(DATASET_PATH / "train" / "other" / f"other_{index}.jpg", (40, 80, 220))
    (DATASET_PATH / "dataset_info.json").write_text(
        '{\n'
        f'  "name": "{DATASET_NAME}",\n'
        '  "classes": ["target", "other"],\n'
        '  "image_size": 96,\n'
        '  "train_count": 8,\n'
        '  "val_count": 0,\n'
        '  "test_count": 0\n'
        '}\n',
        encoding="utf-8",
    )


def main() -> int:
    client = TestClient(app)

    empty_response = client.post(
        "/api/training/start",
        json={
            "dataset_path": "data/exported/dataset_v001",
            "epochs": 1,
            "batch_size": 2,
            "model_type": "tiny_cnn",
        },
    )
    if empty_response.status_code != 400:
        return fail("Empty dataset should return 400", empty_response.text)
    ok("Empty dataset is rejected with a clear error")

    try:
        create_training_dataset()
        ok("Created small training dataset")
    except Exception as exc:
        return fail("Could not create small training dataset", str(exc))

    response = client.post(
        "/api/training/start",
        json={
            "dataset_path": f"data/exported/{DATASET_NAME}",
            "epochs": 1,
            "batch_size": 2,
            "model_type": "tiny_cnn",
        },
    )
    if response.status_code != 200:
        return fail("Training API did not return 200 for valid dataset", response.text)
    data = response.json()
    if not data.get("ok") or data.get("status") != "running":
        return fail("Training API returned ok=false", str(data))
    run_id = data["run_id"]
    for _ in range(90):
        status_response = client.get(f"/api/training/{run_id}/status")
        status_response.raise_for_status()
        status_data = status_response.json()
        if status_data.get("status") == "completed":
            ok("Training API completed one-epoch smoke training")
            break
        if status_data.get("status") == "failed":
            return fail("Training API process failed", status_data.get("log_tail", ""))
        time.sleep(1)
    else:
        return fail("Training API did not complete in time")

    print("\nTraining API smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
