# Python Training Environment

Use Python 3.12.x for both the server MVP and TensorFlow training.

Python 3.14 may remain installed, but this project should use Python 3.12 first on PATH.

## Recommended Check

```powershell
cd <PROJECT_ROOT>
python --version
where.exe python
python -m pip --version
python scripts\check_python_env.py
```

## Optional Virtual Environment

If you want an isolated environment, create a Python 3.12 virtual environment.

```powershell
cd <PROJECT_ROOT>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r server\requirements.txt
python -m pip install -r trainer\requirements.txt
python -c "import tensorflow as tf; print(tf.__version__)"
```

## Trainer Check

After exporting a dataset from the Web UI:

```powershell
python trainer\train_classifier.py --dataset data\exported\<DATASET_NAME> --output data\models\<RUN_NAME> --epochs 2
python tools\copy_model_to_firmware.py --model-dir data\models\<RUN_NAME>
```

If `where.exe python` shows `Python314` before `Python312`, fix PATH or disable Windows App execution aliases.
