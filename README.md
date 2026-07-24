# esp32s3-vision-ai-workflow

ESP32-S3カメラで画像を集め、PCのブラウザでラベル付けし、画像分類モデルを学習してESP32-S3へ書き込むためのローカルLAN向けワークフローです。

検証ボードは Seeed Studio XIAO ESP32S3 Sense です。

## できること

- ESP32-S3をWi-Fiに接続
- ブラウザからESP32-S3のカメラ映像を表示
- ブラウザのCaptureボタンで遠隔撮影
- 撮影画像をPCサーバへアップロード
- ブラウザでラベル付け
- データセット作成
- TensorFlow/Kerasで分類モデルを学習
- TFLite int8へ変換
- ESP32-S3用ファームへモデルを組み込み
- Web UIからESP32-S3へファームを書き込み

## 必要なもの

- Windows PC
- Python 3.12.x
- ESP-IDF 5.x
- ESP32-S3カメラボード
- 同じLANにつながるWi-Fi

## セットアップ

```powershell
cd esp32s3-vision-ai-workflow
python -m pip install -r server\requirements.txt
python -m pip install -r trainer\requirements.txt
```

サーバを起動します。

```powershell
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

ブラウザで開きます。

```text
http://localhost:8000
```

## Wi-Fi設定と撮影ファーム書き込み

Web画面上部の `ESP32-S3 Wi-Fi Settings` を使います。

1. SSID、Password、Server URL、Device IDを入力
2. `Refresh ports`
3. ESP32-S3のCOMポートを選択
4. `Write Wi-Fi firmware`

`Server URL` はPCのLAN IPを使います。

```text
http://PCのLAN_IP:8000/api/images/upload
```

PCのIP候補を調べるには:

```powershell
ipconfig
```

表示されたIPv4アドレスを使ってください。

## ブラウザから遠隔撮影

Wi-Fiファームを書き込んだあと、ESP-IDF monitorでESP32-S3のIPを確認します。

```powershell
cd firmware\capture_upload
idf.py -p COMx monitor
```

ログに表示されるIPを、Web画面上部の `ESP32-S3 URL` に入れます。

```text
http://192.168.x.x
```

その後:

1. `Open camera`
2. ポップアップで映像を確認
3. `Capture`

撮影画像はPCサーバへアップロードされ、画像一覧に表示されます。

## ラベル付けと学習

1. ラベルを作成
2. 画像にラベルを付ける
3. Dataset nameを入れて `Export dataset`
4. Dataset selectでデータセットを選択
5. Epochsを設定
6. `Start training`

学習中は loss / accuracy のグラフが表示されます。

## 推論ファーム書き込み

学習後:

1. Model selectで学習済みモデルを選択
2. `Prepare firmware files`
3. `Refresh ports`
4. COMポートを選択
5. `Write firmware to ESP32-S3`

これでESP32-S3は分類推論ファームになります。

## 注意

- `data/` には撮影画像、ラベル、データセット、学習済みモデルが保存されます。
- `data/` はGitHubへ上げないでください。
- このプロジェクトはローカルLAN内で使う前提です。
- ユーザー認証やクラウド連携はありません。
- `firmware/capture_upload/main/app_config.h` はダミー値入りで同梱しています。自分の環境に合わせてWeb UIから編集できます。
- Wi-Fiパスワード欄は表示/非表示を切り替えられます。

## 主なフォルダ

```text
server/      PC側FastAPIサーバ
web/         ブラウザUI
trainer/     学習とTFLite変換
tools/       モデル変換補助
firmware/    ESP32-S3用ファーム
```
# 追記
## 実行環境の確認結果と初回セットアップ時の注意

### 確認済み環境

- Windows PC
- Python 3.12.7
- ESP-IDF v5.4.4
- Seeed Studio XIAO ESP32S3 Sense
- ESP32-S3はUSB接続時にCOMポートとして認識
- Python依存パッケージは導入済み
- `python -m pip check` の結果、依存関係に問題なし
- Node.js/npmは不要

### PC側の起動

GitHubからZIPでダウンロードした場合、展開後のフォルダー名に注意してください。

```powershell
cd esp32s3-vision-ai-workflow-main
python -m pip install -r server\requirements.txt
python -m pip install -r trainer\requirements.txt
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```
ブラウザで以下を開きます。

```http://localhost:8000```
ESP-IDFについて
idf.py自体はインストールされていますが、通常のPowerShellではPATHに登録されていない場合があります。
その場合は、ESP-IDF PowerShellを使用するか、ESP-IDFの環境設定後に実行してください。
idf.py -p COM3 monitor
初回ファームウェアビルド時の注意
GitHubからダウンロードした直後の状態では、以下のフォルダーが存在しません。

- firmware/capture_upload/managed_components
- firmware/inference_classification/managed_components
- inference_classificationでは、以下のESP-IDFコンポーネントが必要です。
- espressif/esp32-camera
- esp-tflite-micro
- esp_jpeg
- esp-nn
- 
初回ビルド時には、ESP-IDF Component Managerによるコンポーネント取得と、インターネット接続が必要です。

現在確認されている構成上の問題

firmware/capture_upload/CMakeLists.txt は、以下のmanaged componentsを直接参照しています。

- managed_components/espressif__esp_jpeg
- ../inference_classification/managed_components/espressif__esp32-camera
- ../inference_classification/managed_components/espressif__esp-tflite-micro
- ../inference_classification/managed_components/espressif__esp-nn

しかし、capture_upload/main/idf_component.ymlには依存部品が定義されていません。

そのため、GitHubから展開した直後にcapture_uploadを直接ビルドすると、managed componentsが存在せずビルドに失敗する可能性があります。

READMEには、以下の手順を追加する必要があります。

inference_classification側のESP-IDFコンポーネントを取得する

capture_uploadが参照するmanaged componentsを準備する

その後にcapture_uploadをビルドする

動作確認結果

確認した範囲では、以下は動作しました。

FastAPIサーバの起動

Web UIとAPIへのアクセス

画像アップロード

ラベル付け

データセット作成

TensorFlowモデル学習

TFLite変換

ESP32-S3用モデルファイル生成

ESP-IDFコンポーネント取得後のファームウェアビルド

まとめ

Pythonパッケージの追加インストールは不要です。

一方、ファームウェアの初回ビルドにはESP-IDFのmanaged components取得が必要です。また、capture_uploadの依存部品定義とCMakeLists.txtのパス構成について、READMEへの説明追加または

プロジェクト構成の修正が必要です。
