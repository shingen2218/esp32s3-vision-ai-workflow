from io import BytesIO
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.main import app


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def create_dummy_jpeg(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (320, 240), color=color)
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def upload_image(client: TestClient, filename: str, color: tuple[int, int, int]) -> tuple[int, str]:
    response = client.post(
        "/api/images/upload",
        data={"device_id": "ui_contract_test"},
        files={"image": (filename, create_dummy_jpeg(color), "image/jpeg")},
    )
    response.raise_for_status()
    data = response.json()
    return data["image_id"], data["filename"]


def main() -> int:
    client = TestClient(app)

    try:
        first_id, first_filename = upload_image(client, "ui_contract_target.jpg", (220, 40, 40))
        second_id, second_filename = upload_image(client, "ui_contract_other.jpg", (40, 80, 220))
        ok("Uploaded two dummy images")
    except Exception as exc:
        return fail("Could not upload dummy images", str(exc))

    try:
        request_body = {"image_ids": [first_id, second_id], "label": "target"}
        response = client.post("/api/images/batch/labels", json=request_body)
        response.raise_for_status()
        data = response.json()
        if data.get("updated_count") != 2:
            return fail("Batch label did not update two images", str(data))
        ok("Batch label API matches Web UI contract")
    except Exception as exc:
        return fail("Batch label API failed", str(exc))

    try:
        response = client.get("/api/images", params={"limit": 20})
        response.raise_for_status()
        images = response.json().get("images", [])
        updated = [image for image in images if image["id"] in [first_id, second_id]]
        if len(updated) != 2 or any(image["label"] != "target" for image in updated):
            return fail("Image list did not show updated target labels", str(updated))
        ok("Image list returns updated labels")
    except Exception as exc:
        return fail("Image list check failed", str(exc))

    try:
        response = client.get("/api/images/export/multilabel.csv")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/csv" not in content_type:
            return fail("CSV content-type is not text/csv", content_type)
        csv_text = response.text
        header = csv_text.splitlines()[0] if csv_text else ""
        for expected in ["filename", "label", "target", "unknown"]:
            if expected not in header:
                return fail(f"CSV header does not contain {expected}", header)
        if first_filename not in csv_text or second_filename not in csv_text:
            return fail("CSV body does not contain uploaded filenames")
        ok("CSV export API matches Web UI contract")
    except Exception as exc:
        return fail("CSV export API failed", str(exc))

    print("\nUI/API contract smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
