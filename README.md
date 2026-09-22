# AquaSpatial Dataset

**An RGB-D instruction-following dataset for water-surface perception**

[![Dataset status](https://img.shields.io/badge/status-preview-f0ad4e)](#release-status)
[![RGB-D pairs](https://img.shields.io/badge/full_dataset-5%2C000_pairs-1f77b4)](#dataset-overview)
[![Preview pairs](https://img.shields.io/badge/public_preview-40_pairs-2ca02c)](#preview-release)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

AquaSpatial is an RGB-D dataset designed for spatial perception and instruction following by water-surface robots. Each scene combines a synchronized RGB image and 16-bit depth image with object-level annotations and a vision-language navigation instruction. The task requires a model to recognize visible objects and localize the nearest requested target and the nearest obstacle in metric coordinates.

## Release Status

> [!IMPORTANT]
> This repository currently provides a **40-pair preview subset** for inspecting the data format and task design. **The complete AquaSpatial dataset will be made publicly available after the associated paper is accepted.** The full release will include all 5,000 RGB-D pairs, complete annotations, SFT conversations, and official train/validation/test splits.

## Dataset Overview

| Property | Value |
|---|---:|
| RGB-D scene pairs | 5,000 |
| Artificial-pool scenes | 4,000 |
| Outdoor-lake scenes | 1,000 |
| Object annotations | 8,033 |
| Object categories | 17 |
| Objects per scene | 0-6 |
| RGB format | JPEG, 640 x 480 |
| Depth format | 16-bit PNG, 640 x 480 |
| Depth unit | millimetres |
| Annotation outputs | 2D box, center point, depth, distance, direction, azimuth, 3D point |
| SFT inputs | RGB image + depth image + navigation instruction |

The 17 categories are:

`black buoy`, `red buoy`, `yellow buoy`, `green buoy`, `red bottle`, `green bottle`, `blue bottle`, `paper bowl`, `paper box`, `pop can`, `plastic bag`, `little yellow duck`, `white foam`, `grey foam`, `black foam`, `blue and black foam`, and `branch`.

## Preview Release

The public preview contains 40 RGB-D pairs selected to preserve the full dataset's 4:1 environment ratio:

- 32 scenes from an artificial pool
- 8 scenes from outdoor lakes
- coverage of all 17 object categories
- coverage of scenes containing 0 through 6 objects
- coverage of all four SFT response cases

### Artificial pool

<table>
  <tr>
    <td align="center"><img src="samples/rgb/rgb_000104.jpg" width="220"><br><sub>Scene 104 | <a href="samples/depth_16bit/depth_000104.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_000559.jpg" width="220"><br><sub>Scene 559 | <a href="samples/depth_16bit/depth_000559.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_002242.jpg" width="220"><br><sub>Scene 2242 | <a href="samples/depth_16bit/depth_002242.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_003517.jpg" width="220"><br><sub>Scene 3517 | <a href="samples/depth_16bit/depth_003517.png">16-bit depth</a></sub></td>
  </tr>
</table>

### Outdoor lakes

<table>
  <tr>
    <td align="center"><img src="samples/rgb/rgb_004162.jpg" width="220"><br><sub>Scene 4162 | <a href="samples/depth_16bit/depth_004162.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_004199.jpg" width="220"><br><sub>Scene 4199 | <a href="samples/depth_16bit/depth_004199.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_004545.jpg" width="220"><br><sub>Scene 4545 | <a href="samples/depth_16bit/depth_004545.png">16-bit depth</a></sub></td>
    <td align="center"><img src="samples/rgb/rgb_004970.jpg" width="220"><br><sub>Scene 4970 | <a href="samples/depth_16bit/depth_004970.png">16-bit depth</a></sub></td>
  </tr>
</table>

Raw 16-bit depth PNGs may look dark in standard image viewers because their values encode metric depth rather than display intensity. See [Quick Start](#quick-start) for loading and visualization.

## Repository Structure

```text
AquaSpatial-Dataset/
|-- README.md
|-- LICENSE
|-- samples/
|   |-- rgb/                 # 40 RGB JPEG images
|   |-- depth_16bit/         # 40 aligned uint16 depth PNG images
|   |-- label_sample.json    # Object-level labels for the preview scenes
|   |-- sft_sample.json      # Portable RGB-D instruction conversations
|   `-- manifest.csv         # Scene metadata and SHA-256 checksums
`-- scripts/
    `-- prepare_preview.py   # Reproducible preview-subset builder
```

The `scene_id` in `manifest.csv` corresponds to the six-digit suffix in each image filename. RGB and depth files with the same suffix form one aligned pair.

## Annotation Format

Each record in `samples/label_sample.json` has two image names and a list of object annotations:

```json
{
  "images_name": ["rgb_000104.jpg", "depth_000104.png"],
  "annotations": [
    {
      "category": "black buoy",
      "bbox": [186, 255, 208, 274],
      "point": [197, 264],
      "depth_m": 3.061,
      "distance_m": 3.134,
      "direction": "left",
      "azimuth_deg": 12.383,
      "point_3d": [-0.672, 0.056, 3.061]
    }
  ]
}
```

| Field | Description |
|---|---|
| `category` | Object category name |
| `bbox` | Bounding box `[x_min, y_min, x_max, y_max]` in RGB pixels |
| `point` | Integer center point `[u, v]` of the bounding box |
| `depth_m` | Forward depth at the object center, in metres |
| `distance_m` | Ground-plane radial distance `sqrt(x^2 + z^2)`, in metres |
| `direction` | Horizontal direction (`left` or `right`) |
| `azimuth_deg` | Horizontal azimuth; positive values point left |
| `point_3d` | Camera-frame point `[x, y, z]` in metres |

The camera-frame convention uses `x` for lateral displacement (negative left, positive right), `y` for vertical displacement, and `z` for forward depth. Spatial quantities are derived using:

```text
x = (u - cx) * z / fx
y = (v - cy) * z / fy
distance = sqrt(x^2 + z^2)
azimuth = atan2(-x, z)
```

Camera intrinsics used during annotation processing are `fx = 606.416`, `fy = 606.030`, `cx = 330.146`, and `cy = 252.912`.

## SFT Format

Each entry in `samples/sft_sample.json` contains two repository-relative image paths and a two-turn conversation:

```json
{
  "images": [
    "samples/rgb/rgb_000104.jpg",
    "samples/depth_16bit/depth_000104.png"
  ],
  "conversations": [
    {
      "from": "human",
      "value": "You are a water surface robot. <image>\nImage 1 is RGB image. <image>\nImage 2 is depth image. Your task is to navigate to a black buoy. Identify objects in the RGB image and output the positions of the nearest target and the nearest obstacle."
    },
    {
      "from": "gpt",
      "value": "Perception: I observe a red bottle, a green bottle, a green buoy and a black buoy. Localization: [target: black buoy, (3.06,-0.67)], [obstacle: red bottle, (0.82,-0.05)]."
    }
  ]
}
```

Localization coordinates are written as `(z, x)`, where `z` is forward depth and `x` is lateral displacement in metres. The nearest visible instance of the requested category is the target. The nearest visible object from any other category is the obstacle.

The instruction construction supports four scene-response cases:

| Case | Target present | Obstacle present | Localization output |
|---|---:|---:|---|
| Target + obstacle | Yes | Yes | Target and nearest obstacle |
| Target only | Yes | No | Target only |
| Obstacle only | No | Yes | Nearest obstacle only |
| Empty localization | No | No | No localization entry |

## Quick Start

```python
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

root = Path("AquaSpatial-Dataset")
sft = json.loads((root / "samples/sft_sample.json").read_text(encoding="utf-8"))
sample = sft[0]

rgb = np.asarray(Image.open(root / sample["images"][0]).convert("RGB"))
depth_mm = np.asarray(Image.open(root / sample["images"][1]))
depth_m = depth_mm.astype(np.float32) / 1000.0
depth_m[depth_mm == 0] = np.nan

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].imshow(rgb)
axes[0].set_title("RGB")
depth_view = axes[1].imshow(depth_m, cmap="turbo")
axes[1].set_title("Depth (m)")
fig.colorbar(depth_view, ax=axes[1], fraction=0.046)
for axis in axes:
    axis.axis("off")
plt.tight_layout()
plt.show()

print(sample["conversations"][0]["value"])
print(sample["conversations"][1]["value"])
```

## Integrity and Reproducibility

`samples/manifest.csv` records the environment, object categories, instruction target, SFT response case, image dimensions, and SHA-256 checksum of every preview file. The preview can be rebuilt from the private source data with:

```bash
python scripts/prepare_preview.py --source-root /path/to/full/AquaSpatial
```

Validate all image pairs, checksums, JSON alignment, depth bit depth, and README links with:

```bash
python scripts/validate_preview.py
```

## Citation

The associated paper is currently under review. Citation metadata will be added after acceptance. Until then, please cite this repository by its URL if the preview subset is used in academic work.

## License

The code and documentation in this repository are released under the [MIT License](LICENSE). Licensing information for the complete dataset will be provided with the full release after paper acceptance.
