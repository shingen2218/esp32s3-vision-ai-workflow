# Dataset Format

Raw uploads are stored in `data/raw`.

Metadata is stored in `data/metadata/images.sqlite3`.

Exported classification datasets use this layout:

```text
data/exported/dataset_v001/
├─ train/
│  ├─ target/
│  └─ other/
├─ val/
│  ├─ target/
│  └─ other/
├─ test/
│  ├─ target/
│  └─ other/
└─ dataset_info.json
```

`dataset_info.json` contains the dataset name, classes, image size, and split counts.

## Label CSV

The Web UI can also export a label CSV. The current workflow is multi-class classification: labels can have many names, but each image has only one label.

Example:

```text
image_id,filename,label,screw,nut,metal,target,other,unknown
1,img001.jpg,screw,1,0,0,0,0,0
2,img002.jpg,nut,0,1,0,0,0,0
```

- CSV columns are generated from the created label palette.
- `label` contains the assigned label.
- A label column is `1` when the image has that label, otherwise `0`.
- `unknown` means the image is not ready for training.
- `test` is reserved for human review after training.

This does not teach object location. Object detection requires Bounding Box annotations in a later workflow.
