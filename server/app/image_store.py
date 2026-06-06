from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from .config import RAW_IMAGE_DIR
from .database import get_db


def _next_filename(device_id: str) -> str:
    safe_device_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in device_id)
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM images WHERE device_id = ?", (device_id,)).fetchone()[0]
    return f"{safe_device_id}_{count + 1:06d}.jpg"


async def save_uploaded_image(image: UploadFile, device_id: str, captured_at: str | None) -> dict:
    filename = _next_filename(device_id)
    target_path = RAW_IMAGE_DIR / filename
    content = await image.read()
    target_path.write_bytes(content)

    width = None
    height = None
    try:
        with Image.open(target_path) as img:
            width, height = img.size
            if img.format != "JPEG":
                converted = img.convert("RGB")
                converted.save(target_path, format="JPEG", quality=92)
    except Exception:
        # Keep the uploaded file for debugging even if Pillow cannot inspect it.
        pass

    uploaded_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO images (filename, device_id, label, captured_at, uploaded_at, width, height, status)
            VALUES (?, ?, 'unknown', ?, ?, ?, ?, 'unlabeled')
            """,
            (filename, device_id, captured_at, uploaded_at, width, height),
        )
        image_id = cursor.lastrowid

    return {"ok": True, "image_id": image_id, "filename": filename}


def image_url(filename: str) -> str:
    return f"/data/raw/{Path(filename).name}"
