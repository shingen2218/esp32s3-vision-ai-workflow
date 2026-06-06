# esp32s3-vision-ai-workflow

ESP32-S3カメラで画像を撮影し、PCにアップロードして、ブラウザでラベル付けし、画像分類モデルを学習してESP32-S3向けに変換するための軽量ワークフローです。

PC側で学習を行い、ESP32-S3側では撮影、アップロード、推論を担当します。

## できること

- ESP32-S3カメラ画像をPCサーバへアップロード
- ブラウザで画像を見ながらラベル付け
- ラベル付き画像から分類データセットを作成
- TensorFlow/Kerasで小型CNNを学習
- TFLite int8モデルへ変換
- ESP32-S3ファームウェア用のC配列へ変換

## 必要なもの

- Windows PC
- Python 3.12.x
- ESP-IDF
- ESP32-S3カメラボード

検証時の対象ボードは Seeed Studio XIAO ESP32S3 Sense です。別ボードではカメラピン設定の変更が必要になる場合があります。

## 1. Python環境

PowerShellでこのフォルダへ移動します。

```powershell
cd <PROJECT_ROOT>
python --version
where.exe python
python -m pip --version
```

`Python 3.12.x` が使われていることを確認してください。

依存関係を入れます。

```powershell
python -m pip install -r server\requirements.txt
python -m pip install -r trainer\requirements.txt
```

環境確認:

```powershell
python scripts\check_python_env.py
```

## 2. PCサーバ起動

```powershell
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

ブラウザで開きます。

```text
http://localhost:8000
http://localhost:8000/docs
```

## 3. ESP32-S3撮影ファーム設定

次のファイルを開いて、自分の環境に合わせて編集します。

```text
firmware/capture_upload/main/app_config.h
```

主に変更する値:

```c
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_UPLOAD_URL "http://YOUR_PC_IP:8000/api/images/upload"
#define DEVICE_ID "xiao_esp32s3_sense_001"
```

PCのIPアドレスが分からない場合:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\get_pc_ip_hint.ps1
```

シリアルポート確認:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\list_serial_ports.ps1
```

ESP-IDF PowerShellで書き込みます。

```powershell
cd firmware\capture_upload
idf.py -p COMx flash monitor
```

`COMx` は自分の環境のポートに置き換えてください。

## 4. 画像を集める

PCサーバを起動した状態で、ESP32-S3の撮影ボタンを押すと画像がアップロードされます。

ブラウザで `http://localhost:8000` を開くと画像一覧が見えます。

## 5. ラベル付け

ブラウザ上でラベルを作成し、画像に付けます。

- 1枚の画像につけるラベルは1種類
- `unknown` は未ラベル
- `test` は学習後の確認用

不要な `unknown` 画像は画面上のボタンから一括削除できます。

## 6. データセット作成

Web UIのデータセット作成欄で名前を入れてエクスポートします。

例:

```text
dataset_v001
```

出力先:

```text
data/exported/dataset_v001
```

## 7. 学習

Web UIでデータセットを選び、`Start training` を押します。

学習ログには epoch、loss、accuracy、val_loss、val_accuracy が表示されます。

学習結果は次に保存されます。

```text
data/models/
```

## 8. TFLiteをESP32-S3用C配列へ変換

学習後に次を実行します。

```powershell
python scripts\inspect_tflite_model.py
python tools\copy_model_to_firmware.py --model-dir data\models\<TRAIN_RUN_DIR>
```

出力先:

```text
firmware/inference_classification/main/model_data.cc
firmware/inference_classification/main/model_data.h
```

## 9. 推論ファームビルド

ESP-IDF PowerShellで実行します。

```powershell
cd firmware\inference_classification
idf.py -p COMx flash monitor
```

## 重要な注意

- `data/` には撮影画像、ラベル、学習済みモデルが保存されます。
- Wi-Fiパスワードや個人データを公開しないよう注意してください。
- ESP32-S3実機への書き込み、長時間撮影、推論ファームの動作は環境により調整が必要です。

## 詳細資料

必要に応じて `docs/` を参照してください。
