from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, RAW_IMAGE_DIR, ensure_data_directories
from .database import init_db
from .routes import datasets, firmware, images, labels, training

ensure_data_directories()
init_db()

app = FastAPI(title="ESP32-S3 Vision Workflow")
app.include_router(images.router)
app.include_router(labels.router)
app.include_router(datasets.router)
app.include_router(training.router)
app.include_router(firmware.router)

app.mount("/data/raw", StaticFiles(directory=RAW_IMAGE_DIR), name="raw-images")
app.mount("/", StaticFiles(directory=PROJECT_ROOT / "web", html=True), name="web")
