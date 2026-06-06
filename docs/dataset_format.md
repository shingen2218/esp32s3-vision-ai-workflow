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

## Multi-label CSV

The Web UI can also export a multi-label classification CSV. This is useful when one image can have several labels such as `screw`, `metal`, `front`, and `defect`.

Example:

```text
image_id,filename,labels,screw,nut,metal,plastic,front,side,normal,defect
1,img001.jpg,screw;metal;front,1,0,1,0,1,0,1,0
2,img002.jpg,nut;metal;side,0,1,1,0,0,1,1,0
```

- CSV columns are generated from the created label palette.
- `labels` contains the assigned labels separated by semicolons.
- A label column is `1` when the image has that label, otherwise `0`.
- `target`, `other`, and `unknown` are included only as normal labels when they exist.

This is multi-label classification. It does not teach object location. Object detection requires Bounding Box annotations in a later workflow.
