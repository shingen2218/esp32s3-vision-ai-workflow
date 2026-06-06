import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_IMAGE_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"
EXPORTED_DIR = DATA_DIR / "exported"
MODEL_DIR = DATA_DIR / "models"
DATABASE_PATH = METADATA_DIR / "images.sqlite3"

DEFAULT_CLASSES = ["target", "other"]
DEFAULT_IMAGE_SIZE = 96
CLASSIFICATION_CONFIG_PATH = METADATA_DIR / "classification_config.json"


def ensure_data_directories() -> None:
    for path in [RAW_IMAGE_DIR, METADATA_DIR, EXPORTED_DIR, MODEL_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def load_classification_config() -> dict:
    ensure_data_directories()
    if not CLASSIFICATION_CONFIG_PATH.exists():
        default_config = {
            "classes": DEFAULT_CLASSES,
            "input_width": DEFAULT_IMAGE_SIZE,
            "input_height": DEFAULT_IMAGE_SIZE,
            "input_channels": 3,
        }
        CLASSIFICATION_CONFIG_PATH.write_text(json.dumps(default_config, indent=2), encoding="utf-8")
        return default_config
    return json.loads(CLASSIFICATION_CONFIG_PATH.read_text(encoding="utf-8"))
