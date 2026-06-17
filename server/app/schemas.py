from pydantic import BaseModel, Field


class LabelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=64)


class LabelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class BatchLabelUpdate(BaseModel):
    image_ids: list[int] = Field(min_length=1)
    label: str | None = Field(default=None, min_length=1, max_length=128)
    label_names: list[str] | None = None


class ImageLabelsUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=128)
    label_names: list[str] | None = None


class BatchTestReserveUpdate(BaseModel):
    image_ids: list[int] = Field(min_length=1)
    reserved_for_test: bool = True


class DatasetExportRequest(BaseModel):
    dataset_name: str = Field(default="dataset_v001", min_length=1, max_length=80)
    train_ratio: float = 0.7
    val_ratio: float = 0.2
    test_ratio: float = 0.1
    image_size: int = 96
    dataset_type: str = "classification"


class TrainingStartRequest(BaseModel):
    dataset_path: str
    epochs: int = 30
    batch_size: int = 16
    model_type: str = "tiny_cnn"


class ModelExportRequest(BaseModel):
    dataset_path: str | None = None


class FirmwareBuildRequest(BaseModel):
    clean: bool = False


class FirmwareFlashRequest(BaseModel):
    port: str = Field(min_length=3, max_length=32)
    firmware: str = "inference_classification"
    target: str | None = None
    force_build: bool = False


class WifiConfigUpdate(BaseModel):
    ssid: str = Field(min_length=1, max_length=128)
    password: str | None = Field(default=None, max_length=128)
    server_upload_url: str = Field(min_length=1, max_length=256)
    device_id: str = Field(min_length=1, max_length=128)


class RemoteCameraRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=256)
