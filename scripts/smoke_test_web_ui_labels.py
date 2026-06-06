from io import BytesIO
from pathlib import Path
import os
import subprocess
import sys
import time

from PIL import Image
from playwright.sync_api import sync_playwright
import requests


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
SCREENSHOT_PATH = ARTIFACT_DIR / "ui_labels.png"
DOWNLOAD_DIR = ARTIFACT_DIR / "downloads"
SERVER_PORT = int(os.environ.get("WEB_UI_LABEL_TEST_PORT", "8011"))
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
LABEL_NAME = f"screw_ui_{int(time.time())}"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def server_is_running() -> bool:
    try:
        return requests.get(f"{SERVER_URL}/docs", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def start_server_if_needed() -> subprocess.Popen | None:
    if server_is_running():
        ok("Server is already running")
        return None
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(SERVER_PORT),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for _ in range(30):
        if server_is_running():
            ok("Started test server")
            return process
        time.sleep(0.5)
    raise RuntimeError(f"Could not start server on {SERVER_URL}")


def create_dummy_jpeg(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (320, 240), color=color)
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def upload_dummy_images() -> None:
    for filename, color in [
        ("ui_label_red.jpg", (220, 40, 40)),
        ("ui_label_blue.jpg", (40, 80, 220)),
    ]:
        response = requests.post(
            f"{SERVER_URL}/api/images/upload",
            data={"device_id": "ui_label_test"},
            files={"image": (filename, create_dummy_jpeg(color), "image/jpeg")},
            timeout=10,
        )
        response.raise_for_status()
    ok("Uploaded label UI test images")


def main() -> int:
    ARTIFACT_DIR.mkdir(exist_ok=True)
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    server_process = None
    try:
        server_process = start_server_if_needed()
        upload_dummy_images()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.route("**/data/raw/**", lambda route: route.abort())
            page.goto(SERVER_URL, wait_until="domcontentloaded")
            page.locator(".imageCard").first.wait_for(timeout=10000)
            ok("Opened Web UI")

            page.locator("#newLabelInput").fill(LABEL_NAME)
            page.locator("#addLabelButton").click()
            page.locator("#labelPalette .label-chip-button", has_text=LABEL_NAME).wait_for(timeout=10000)
            page.wait_for_function(
                "(labelName) => [...document.querySelector('#deleteLabelSelect').options].some((option) => option.value === labelName)",
                arg=LABEL_NAME,
            )
            ok("Created label through UI")

            checkboxes = page.locator(".image-select-checkbox")
            checkboxes.nth(0).check()
            checkboxes.nth(1).check()
            page.locator("#selectedCount", has_text="2").wait_for(timeout=5000)
            ok("Selected two images")

            page.locator("#labelPalette .label-chip-button", has_text=LABEL_NAME).click()
            page.locator(".label-chip", has_text=LABEL_NAME).first.wait_for(timeout=10000)
            ok("Applied palette label to selected images")

            with page.expect_download() as download_info:
                page.locator("#downloadCsvButton").click()
            download = download_info.value
            csv_path = DOWNLOAD_DIR / download.suggested_filename
            download.save_as(csv_path)
            csv_text = csv_path.read_text(encoding="utf-8")
            if LABEL_NAME not in csv_text.splitlines()[0]:
                return fail("Downloaded CSV does not contain created label column", csv_text.splitlines()[0])
            ok("Downloaded CSV with created label column")

            page.locator("#deleteLabelSelect").select_option(LABEL_NAME)
            page.locator("#deleteLabelButton").click()
            page.locator("#statusMessage", has_text=f"Deleted label {LABEL_NAME}").wait_for(timeout=10000)
            if page.locator("#labelPalette .label-chip-button", has_text=LABEL_NAME).count() != 0:
                return fail("Deleted label is still visible in label palette")
            if page.locator(".imageCard .label-chip", has_text=LABEL_NAME).count() != 0:
                return fail("Deleted label is still visible on an image card")
            ok("Deleted label through UI and removed it from images")

            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            ok(f"Saved screenshot: {SCREENSHOT_PATH}")
            browser.close()

        print("\nWeb UI label palette smoke test passed.")
        return 0
    except Exception as exc:
        return fail("Web UI label palette smoke test failed", str(exc))
    finally:
        if server_process is not None:
            server_process.terminate()


if __name__ == "__main__":
    sys.exit(main())
