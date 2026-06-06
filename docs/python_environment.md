# Python環境

## 推奨

Python 3.12.x

このプロジェクトでは server / web / tools / trainer をPython 3.12で確認します。Python 3.14が残っていても構いませんが、プロジェクト実行時には使いません。

## 確認コマンド

```powershell
python --version
where.exe python
python -m pip --version
python -c "import sys; print(sys.executable)"
python scripts\check_python_env.py
```

## 正常例

```text
Python 3.12.7
C:\Users\<YOU>\AppData\Local\Programs\Python\Python312\python.exe
```

## 異常例

```text
C:\Users\<YOU>\AppData\Local\Programs\Python\Python314\python.exe
C:\Users\<YOU>\AppData\Local\Microsoft\WindowsApps\python.exe
```

## 対策

- Python 3.12をpython.org版で入れる
- インストール時に `Add python.exe to PATH` にチェックを入れる
- WindowsAppsの `python.exe` エイリアスをOFFにする
- 必要ならPython 3.14をアンインストールする
- PATHを修正したらPowerShellを開き直す
