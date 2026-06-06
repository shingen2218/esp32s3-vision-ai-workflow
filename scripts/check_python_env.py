import importlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MPL_CACHE = ROOT / "data" / ".cache" / "matplotlib"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def ng(message: str) -> None:
    print(f"[NG] {message}")


def module_import_check(module_name: str, display_name: str | None = None) -> bool:
    label = display_name or module_name
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        if version:
            ok(f"{label} import: {version}")
        else:
            ok(f"{label} import")
        return True
    except Exception as exc:
        ng(f"{label} import failed")
        print(f"     Detail: {exc}")
        if module_name == "tensorflow":
            print("     Run:")
            print("     python -m pip install -r trainer\\requirements.txt")
        return False


def main() -> int:
    failed = False
    executable = sys.executable
    version = sys.version_info

    if "Python312" in executable and version.major == 3 and version.minor == 12:
        ok(f"Python executable: {executable}")
    else:
        failed = True
        if "Python314" in executable:
            ng(f"Python executable points to Python314: {executable}")
        else:
            ng(f"Python executable is not Python312: {executable}")

    version_text = f"{version.major}.{version.minor}.{version.micro}"
    if version.major == 3 and version.minor == 12:
        ok(f"Python version: {version_text}")
    else:
        failed = True
        ng(f"Python version: {version_text}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
        ok(f"pip is available: {result.stdout.strip()}")
    except Exception as exc:
        failed = True
        ng("pip check failed")
        print(f"     Detail: {exc}")

    if not module_import_check("fastapi"):
        failed = True
    if not module_import_check("PIL", "pillow"):
        failed = True
    if not module_import_check("tensorflow"):
        failed = True

    if "WindowsApps" in executable:
        warn("WindowsApps python.exe is active. Disable App execution aliases if this causes trouble.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
