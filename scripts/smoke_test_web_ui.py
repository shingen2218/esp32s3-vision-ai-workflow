from io import BytesIO
from pathlib import Path
import os
import subprocess
import sys
import time

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
import requests


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
SCREENSHOT_PATH = ARTIFACT_DIR / "ui_after_fix.png"
DOWNLOAD_DIR = ARTIFACT_DIR / "downloads"
SERVER_PORT = int(os.environ.get("WEB_UI_TEST_PORT", "8010"))
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def server_is_running() -> bool:
    try:
        response = requests.get(f"{SERVER_URL}/docs", timeout=2)
        return response.status_code == 200
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
    raise RuntimeError(f"Could not start FastAPI server on {SERVER_URL}")


def create_dummy_jpeg(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (320, 240), color=color)
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def upload_dummy_images() -> None:
    samples = [
        ("ui_browser_red.jpg", (230, 40, 40)),
        ("ui_browser_blue.jpg", (40, 80, 230)),
    ]
    for filename, color in samples:
        response = requests.post(
            f"{SERVER_URL}/api/images/upload",
            data={"device_id": "ui_browser_test"},
            files={"image": (filename, create_dummy_jpeg(color), "image/jpeg")},
            timeout=10,
        )
        response.raise_for_status()
    ok("Uploaded browser test images")


def main() -> int:
    ARTIFACT_DIR.mkdir(exist_ok=True)
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    server_process = None

    try:
        server_process = start_server_if_needed()
        upload_dummy_images()

        console_messages: list[str] = []
        network_events: list[str] = []
        debug_notes: list[str] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.route("**/data/raw/**", lambda route: route.abort())

            page.on("console", lambda message: console_messages.append(f"{message.type}: {message.text}"))
            page.on("pageerror", lambda error: console_messages.append(f"pageerror: {error}"))
            page.on(
                "request",
                lambda request: network_events.append(f"request {request.method} {request.url}")
                if "/api/" in request.url
                else None,
            )
            page.on(
                "requestfailed",
                lambda request: network_events.append(f"failed {request.method} {request.url} {request.failure}")
                if "/api/" in request.url
                else None,
            )
            page.on(
                "response",
                lambda response: network_events.append(f"{response.status} {response.url}")
                if "/api/" in response.url
                else None,
            )

            page.goto(SERVER_URL, wait_until="domcontentloaded")
            page.locator(".imageCard").first.wait_for(timeout=10000)
            ok("Opened Web UI")

            cards = page.locator(".imageCard")
            if cards.count() < 2:
                return fail("Less than two image cards are visible", f"count={cards.count()}")
            ok("Image cards are visible")

            checkboxes = page.locator(".image-select-checkbox")
            if checkboxes.count() < 2:
                return fail("Checkboxes are not visible in image cards", f"count={checkboxes.count()}")
            ok("Checkboxes are present in DOM")

            checkboxes.nth(0).check()
            checkboxes.nth(1).check()
            page.locator("#selectedCount").wait_for(state="visible")
            selected_text = page.locator("#selectedCount").inner_text()
            if "2" not in selected_text:
                return fail("Selected count did not become 2", selected_text)
            ok("Selected count updated to 2")

            bulk_target_button = page.locator("#bulkLabelButtons button", has_text="target").first
            if bulk_target_button.count() == 0:
                return fail("Bulk target button was not found")
            bulk_target_button.click()
            debug_notes.append(f"status after bulk click: {page.locator('#statusMessage').inner_text(timeout=1000)}")
            debug_notes.append(f"selected after bulk click: {page.locator('#selectedCount').inner_text(timeout=1000)}")
            page.locator("#statusMessage", has_text="Applied target").wait_for(timeout=10000)
            page.locator("#selectedCount").wait_for(state="visible")
            page.locator(".label-chip", has_text="target").first.wait_for(timeout=5000)
            if not any("/api/images/batch/labels" in event and event.startswith("200 ") for event in network_events):
                return fail("Bulk label Network event was not observed", "\n".join(network_events[-10:]))
            ok("Bulk Label applied target in browser")

            with page.expect_download() as download_info:
                page.locator("#downloadCsvButton").click()
            download = download_info.value
            download_path = DOWNLOAD_DIR / download.suggested_filename
            download.save_as(download_path)
            if not download_path.exists():
                return fail("CSV download file was not saved", str(download_path))
            csv_text = download_path.read_text(encoding="utf-8")
            for expected in ["filename", "target", "test", "unknown"]:
                if expected not in csv_text.splitlines()[0]:
                    return fail(f"CSV header does not contain {expected}", csv_text.splitlines()[0])
            ok("CSV download worked in browser")

            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            ok(f"Saved screenshot: {SCREENSHOT_PATH}")

            if console_messages:
                print("\nConsole messages:")
                for message in console_messages[-20:]:
                    print(f"  {message}")

            if network_events:
                print("\nAPI network events:")
                for event in network_events[-20:]:
                    print(f"  {event}")

            browser.close()

        print("\nWeb UI browser smoke test passed.")
        return 0
    except PlaywrightTimeoutError as exc:
        detail = str(exc)
        if "debug_notes" in locals() and debug_notes:
            detail += "\nDebug notes:\n" + "\n".join(debug_notes[-10:])
        if "console_messages" in locals() and console_messages:
            detail += "\nConsole messages:\n" + "\n".join(console_messages[-20:])
        if "network_events" in locals() and network_events:
            detail += "\nAPI network events:\n" + "\n".join(network_events[-20:])
        return fail("Playwright timed out while testing the Web UI", detail)
    except Exception as exc:
        return fail("Web UI browser smoke test failed", str(exc))
    finally:
        if server_process is not None:
            server_process.terminate()


if __name__ == "__main__":
    sys.exit(main())
