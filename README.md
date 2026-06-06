# esp32s3-vision-workflow

ESP32-S3カメラで撮影した画像をPCへアップロードし、ラベル付け、分類データセット作成、学習、TFLite int8変換、C配列変換、ESP-IDFファームウェアへの組み込みまでを扱うMVPです。

## 役割分担

- ESP32-S3: JPEG撮影、HTTPアップロード、推論
- PC: 画像保存、SQLiteメタデータ管理、ラベル付け、データセット分割、学習、量子化、モデル変換

ESP32-S3上では学習しません。最初のMVPは画像分類のみを対象にします。

## セットアップ

```bash
cd esp32s3-vision-workflow
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
```

Windows PowerShell:

```powershell
cd esp32s3-vision-workflow
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r server\requirements.txt
```

## Windows / Python 3.12での確認手順

このプロジェクトでは Python 3.12.x を推奨します。server / web / tools / trainer を同じPython 3.12環境で確認します。Python 3.14がインストール済みでも、プロジェクトでは使いません。

### Python 3.12環境確認

```powershell
cd <PROJECT_ROOT>
python --version
where.exe python
python -m pip --version
python scripts\check_python_env.py
```

`where.exe python` で `Python312` が先頭に出ることを確認してください。`Python314` や `WindowsApps` が先頭に出る場合はPATHまたはWindowsのアプリ実行エイリアスを見直します。

### サーバMVP確認

```powershell
python -m pip install -r server\requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\run_smoke_test.ps1
```

### サーバ起動

```powershell
python -m uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザ:

```text
http://localhost:8000
http://localhost:8000/docs
```

### trainer環境確認

```powershell
python -m pip install -r trainer\requirements.txt
python -c "import tensorflow as tf; print(tf.__version__)"
```

### 学習スモークテスト

```powershell
python scripts\smoke_test_trainer.py
```

### TFLite C配列変換確認

```powershell
python scripts\smoke_test_model_export.py
```

### TFLite推論確認

```powershell
python scripts\inspect_tflite_model.py
python scripts\smoke_test_tflite_inference.py
```

### ESP-IDFビルド前確認

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_espidf_env.ps1
```

### ESP32-S3ファームウェアビルド

ESP-IDF PowerShellを開いてから実行します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1
```

Python環境の詳しい確認とトラブルシューティングは `docs/python_environment.md` を参照してください。

## 現在の検証状況

- PC側サーバ、Web UI、ラベル付け、データセット出力、学習、TFLite変換、C配列変換はPC上で確認しています。
- ESP32-S3向けファームウェアはビルド確認用の雛形を含みます。
- ESP32-S3実機への書き込み、長時間撮影、推論ファームの実機動作は今後の確認項目です。

## 段階チェック

1. Server smoke test
2. Web UI manual test
3. Dataset export test
4. Python 3.12 trainer test
5. TFLite to C array test
6. ESP32-S3 capture firmware build
7. ESP32-S3 inference firmware build
8. ESP32-S3実機撮影
9. ESP32-S3実機推論

## ESP32-S3実機前チェックリスト

- [ ] Python 3.12が使われている
- [ ] server smoke test が通る
- [ ] http://localhost:8000 が開く
- [ ] http://localhost:8000/docs が開く
- [ ] Web UIで画像にラベル付けできる
- [ ] dataset export ができる
- [ ] trainer smoke test が通る
- [ ] model_int8.tflite が生成される
- [ ] model_data.cc / model_data.h が生成される
- [ ] ESP-IDFが使える
- [ ] capture_upload firmware がbuildできる
- [ ] inference_classification firmware がbuildできる

## サーバ起動

```bash
uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000
```

または:

```bash
bash server/run_server.sh
```

ブラウザで開きます。

```text
http://localhost:8000/
```

## 画像アップロード

ESP32-S3ファームからは `POST /api/images/upload` にmultipartで送信します。PCから動作確認する場合:

```bash
curl -F "image=@sample.jpg" -F "device_id=esp32s3_001" http://localhost:8000/api/images/upload
```

保存先:

```text
data/raw/
data/metadata/images.sqlite3
```

## Web UI手動確認

1. サーバ起動

```powershell
python -m uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000
```

2. サンプル画像生成

```powershell
python scripts\create_manual_test_images.py
```

3. サンプル画像アップロード

```powershell
python scripts\upload_manual_test_images.py --server http://localhost:8000
```

4. ブラウザで開く

```text
http://localhost:8000
```

5. 画像を確認し、赤い円画像は `target`、青い四角画像は `other` にラベル付けします。

6. Web UIから `dataset_manual_test` を作成します。

7. `data/exported/dataset_manual_test` ができていることを確認します。

## 実画像の一括ラベル付けとCSV出力

ESP32-S3から画像アップロードが成功したら、Web UIで実画像を確認します。

```text
http://localhost:8000
```

操作:

- `New label` に `screw` や `metal` など任意のラベル名を入れて `Add Label` で作成します
- `Select label to delete` で作成済みラベルを選び、`Delete Label` を押すと、そのラベル自体を削除し、全画像からも外します
- `unknown` は未ラベル画像のためのシステムラベルなので削除できません
- `test` はテスト用画像を示すシステムラベルなので削除できません
- 作成済みラベルはチップ状のラベルパレットに表示されます
- 画像カードをクリックすると右側に拡大表示されます
- 画像カード左上のチェックボックスで複数画像を選択します
- ラベルパレットのチップをクリックすると、拡大表示中の画像またはチェック済み画像のラベルをその1種類に置き換えます
- `test` チップはテスト用画像の専用ラベルです。`unknown` や他ラベルとは同居せず、画像のラベルを `test` だけに置き換えます
- 同じラベルをもう一度押すか、画像カードや拡大表示内のラベル横の `x` を押すと、その画像は `unknown` に戻ります
- `Bulk Label` のチップを押すと、選択画像へ同じラベルを一括付与します
- `Select all` は現在表示中の画像をすべて選択します
- `Clear` は選択を解除します
- `Download label CSV` でラベルCSVを出力します

学習は **1画像=1ラベル** の多クラス分類です。ラベルの種類はいくつでも作れますが、1枚の画像に同時に複数ラベルは付けません。

CSV形式:

```text
image_id,filename,label,screw,nut,metal,unknown
37,xiao_esp32s3_sense_001_000011.jpg,screw,1,0,0,0
```

CSV列は作成済みラベルに応じて増えます。`label` がその画像の正解ラベルで、後続の列はone-hot表現です。

これは物体検出ではなく **多クラス画像分類** です。画像内の物体位置を学習したい場合は、Phase 2でBounding Boxアノテーションが必要です。

### Web UI動作確認

サーバを再起動します。

```powershell
cd <PROJECT_ROOT>
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

ブラウザを開きます。

```text
http://localhost:8000
```

表示済みのページが古いJavaScriptを使っている場合があるため、`Ctrl+F5` で再読み込みしてください。

確認項目:

- 画像カードをクリックして拡大できる
- チェックボックスで複数画像を選択できる
- 選択数が表示される
- `New label` で任意ラベルを作成できる
- ラベルパレットからクリックで付け外しできる
- `Bulk Label` で選択画像に任意ラベルを付けられる
- 画像カードにラベルが反映される
- `Download label CSV` でCSVが保存される
- CSVを開くと `filename` と `target` / `other` / `unknown` 列がある

### PlaywrightによるWeb UI自動確認

実ブラウザ相当のDOM、Console、Network、クリック操作、CSVダウンロードを確認します。

初回のみ:

```powershell
python -m pip install playwright
python -m playwright install chromium
```

実行:

```powershell
python scripts\smoke_test_web_ui.py
python scripts\smoke_test_labels.py
python scripts\smoke_test_web_ui_labels.py
```

成功するとスクリーンショットとCSVダウンロード結果が保存されます。

```text
artifacts/ui_after_fix.png
artifacts/downloads/label_dataset.csv
```

## タグ付け

Web UIで画像を選び、`target` / `other` / `unknown` を押します。

キーボード:

- `1`: target
- `2`: other
- `u`: unknown
- `n`: next

## データセット作成

Web UIのDataset Exportを使うか、CLIで実行します。

```bash
python tools/make_dataset.py --name dataset_v001 --image-size 96
```

出力:

```text
data/exported/dataset_v001/
├─ train/
├─ val/
├─ test/
└─ dataset_info.json
```

Dataset Exportでは次の画像は学習用データセットに入りません。

- `unknown` または `unlabeled` の画像
- `test` ラベルを付けた画像

`dataset_info.json` には `excluded_unknown_count`、`review_test_count`、`test_label` が記録されます。

### unknown画像の一括削除

Web UIの `Delete unknown images` を押すと、`unknown` / `unlabeled` の画像をDBと `data/raw/` から一括削除します。まだ判断していない画像も消えるため、必要な画像を先にラベル付けしてください。

### テスト用画像

学習後に人間が見て評価したい画像には、`test` ラベルだけを付けます。

```text
例:
学習に使うscrew画像: screw
テスト用画像: test

学習に使うnut画像: nut
テスト用画像: test
```

Dataset Export時に、`test` の画像は `data/exported/<dataset>/review_test/` に出力されます。学習用の `train/` や `val/` には入りません。

学習後に `Test dataset images` を押すと、学習済みモデルで `review_test/` 内の画像を推論し、予測ラベルと各ラベル確率を表示します。`test` は正解ラベルを持たないレビュー用ラベルなので、正解/不正解は人が画像を見て判断します。

### データセットと学習モデルの選択

Web UIのTraining欄には `Dataset select` と `Model select` があります。

- `Dataset select`: テストしたい `review_test/` を含むデータセットを選びます
- `Model select`: 学習済みモデルを選びます
- `Model select` を選ぶと、そのモデル作成時に使ったデータセットが分かる場合は `Dataset path` も自動で切り替わります
- `Test dataset images` は、選択中のモデルと選択中のデータセットを使って `review_test/` の画像を推論します

古いモデルと新しいデータセットを組み合わせることもできますが、ラベル名が一致しているモデルとデータセットを選ぶのが基本です。

## 学習

```bash
python trainer/train_classifier.py --dataset data/exported/dataset_v001 --epochs 30 --batch-size 16
```

出力:

```text
data/models/latest/model.keras
data/models/latest/labels.txt
```

Web UIから `Start training` した場合は、ログ欄に現在のepochが表示されます。

```text
Training progress: epoch 12/30
```

Training欄には学習曲線も表示されます。

- `Loss`: `loss` と `val_loss` が下がるほど良い
- `Accuracy`: `accuracy` と `val_accuracy` が上がるほど良い
- `loss` だけ下がって `val_loss` が上がる場合は、学習画像だけを覚える過学習の可能性があります
- 複数の `Model select` を切り替えると、過去モデルの学習曲線を見比べられます

Epochsを増やして比較する場合は、`30 -> 50 -> 100` のように段階的に試し、`val_loss` と `val_accuracy` を重視します。

### 対象が小さく写る場合

分類モデルは画像全体からラベルを判断します。対象が局所的に小さく写っている場合は、まず次を試します。

- 対象が大きく写る距離で撮影する
- 背景や角度を変えた画像を増やす
- 対象を中央に寄せる
- 画像を切り抜いて対象が大きく入るデータセットを作る

対象を枠で囲んで「どこにあるか」まで学習したい場合は、画像分類ではなく物体検出の領域です。Phase 2でBounding Boxアノテーションと検出モデルに進みます。

学習済みモデルで1枚の画像を確認する場合:

```bash
python trainer/predict_classifier.py --model data/models/latest/model.keras --labels data/models/latest/labels.txt --image data/raw/sample.jpg --image-size 96
```

出力例:

```text
prediction:
  screw: 0.8721
  nut: 0.1014
  metal: 0.0265
result: screw
```

## TFLite変換

```bash
python trainer/export_tflite.py --model data/models/latest/model.keras --dataset data/exported/dataset_v001 --out-dir data/models/latest
```

TensorFlowの通常ログを抑えたい場合:

```bash
python trainer/export_tflite.py --model data/models/latest/model.keras --dataset data/exported/dataset_v001 --out-dir data/models/latest --quiet-tf-log
```

出力:

```text
data/models/latest/model_float32.tflite
data/models/latest/model_int8.tflite
```

## C配列変換

```bash
python tools/convert_tflite_to_c_array.py --input data/models/latest/model_int8.tflite --cc firmware/inference_classification/main/model_data.cc --header firmware/inference_classification/main/model_data.h
```

学習スモークで生成したモデルを確認する場合:

```powershell
python scripts\inspect_tflite_model.py
python scripts\smoke_test_tflite_inference.py
python scripts\smoke_test_model_export.py
```

## ESP32-S3撮影ファーム

ESP-IDF PowerShellを開いてから作業します。

```powershell
idf.py --version
powershell -ExecutionPolicy Bypass -File scripts\check_espidf_env.ps1
```

XIAO ESP32S3 Sense向けに `esp32-camera` managed componentを使います。AI Thinker ESP32-CAM用のピン設定は流用しません。Wi-FiやPCサーバURLはGit管理しないため、最初に設定ファイルをコピーします。

```powershell
copy firmware\capture_upload\main\app_config.example.h firmware\capture_upload\main\app_config.h
notepad firmware\capture_upload\main\app_config.h
```

PCのLAN IP候補を確認します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\get_pc_ip_hint.ps1
```

`app_config.h` の `SERVER_UPLOAD_URL` は次の形式にします。

```c
#define SERVER_UPLOAD_URL "http://PCのLAN_IP:8000/api/images/upload"
```

Wi-Fi SSIDとパスワードも `app_config.h` に設定します。このファイルはGit管理外です。パスワードをログやチャットに貼らないでください。

```bash
cd firmware/capture_upload
idf.py set-target esp32s3
idf.py build
```

XIAO ESP32S3 Senseではカメラピン設定とPSRAM設定が重要です。設定は `xiao_esp32s3_sense_camera_pins.h` と `sdkconfig.defaults` に分けています。

### ESP32-S3実機アップロード確認

PCサーバを起動します。

```powershell
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

ブラウザで確認します。

```text
http://localhost:8000
http://localhost:8000/docs
```

COMポートを確認します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\list_serial_ports.ps1
```

ESP-IDF PowerShellでflash/monitorします。

```powershell
cd firmware\capture_upload
idf.py -p COMx flash monitor
```

`COMx` は検出されたCOMポートに置き換えてください。

期待ログ:

```text
wifi connected
got ip: ...
camera init ok
ready: press BOOT/GPIO0 to capture and upload
capture button pressed
captured jpeg size=... bytes
upload status=200
server response: {"ok":true,...}
```

`capture_upload` は自動連写ではなく、起動後に待機し、BOOTボタン(GPIO0)を押したタイミングで1枚だけ撮影してアップロードします。もう一度撮りたい場合は、再度BOOTボタンを押します。Reset直後にBOOTを押しっぱなしにすると書き込みモードに入るため、通常起動ログが出てから押してください。

COMポートが出ない場合は、データ通信できるUSBケーブルか、BOOTを押しながら接続、Reset、Windowsのデバイスマネージャーを確認してください。アップロードが失敗する場合は、ESP32-S3とPCが同じLANにいるか、`SERVER_UPLOAD_URL` がPCのLAN IPになっているか、Windows Firewallがポート8000を許可しているか確認します。

### 既存画像を使わない場合

現在保存済みの画像をラベル付け対象から外したい場合は、削除ではなく退避できます。

```powershell
python scripts\archive_current_images.py
```

実行すると `data/raw/*.jpg` は `data/archived/raw_日時/` に移動され、SQLiteの `images` テーブルは空になります。元のSQLiteは `data/archived/images_日時.sqlite3` にバックアップされます。

## ESP32-S3推論ファーム

```bash
cd firmware/inference_classification
idf.py set-target esp32s3
idf.py build
```

`model_data.cc` / `model_data.h` はC配列変換ツールで更新します。

両方をまとめてビルドする場合:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1
```

クリーンビルドが必要な場合:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_esp32_firmware.ps1 -Clean
```

まず `capture_upload` でカメラ初期化と画像アップロードが通ることを確認してから、推論ファームの実機flashへ進みます。

## 現在の制限

- 認証なし、ローカルLAN前提
- 画像分類のみ
- 学習ジョブは簡易的に同期実行
- ESP32-S3推論ファームは雛形で、実機のピン設定とTFLite Microコンポーネント設定が必要
- Label Studio連携と物体検出はPhase 2

## 今後の物体検出拡張

`docs/future_detection_plan.md` にPhase 2の設計をまとめています。
