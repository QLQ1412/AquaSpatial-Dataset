"""Validate the public AquaSpatial preview release."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    with (ROOT / "samples/manifest.csv").open(encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    labels = json.loads((ROOT / "samples/label_sample.json").read_text(encoding="utf-8"))
    sft = json.loads((ROOT / "samples/sft_sample.json").read_text(encoding="utf-8"))

    assert len(manifest) == len(labels) == len(sft) == 40
    assert len(list((ROOT / "samples/rgb").glob("*.jpg"))) == 40
    assert len(list((ROOT / "samples/depth_16bit").glob("*.png"))) == 40

    label_by_rgb = {record["images_name"][0]: record for record in labels}
    categories = set()
    for row, sample in zip(manifest, sft):
        scene_id = int(row["scene_id"])
        rgb_name = f"rgb_{scene_id:06d}.jpg"
        depth_name = f"depth_{scene_id:06d}.png"
        rgb_path = ROOT / row["rgb_path"]
        depth_path = ROOT / row["depth_path"]
        assert rgb_path.name == rgb_name
        assert depth_path.name == depth_name
        assert rgb_path.is_file() and depth_path.is_file()
        assert sample["images"] == [row["rgb_path"], row["depth_path"]]
        assert rgb_name in label_by_rgb
        assert sha256(rgb_path) == row["rgb_sha256"]
        assert sha256(depth_path) == row["depth_sha256"]

        with Image.open(rgb_path) as rgb, Image.open(depth_path) as depth:
            assert rgb.size == depth.size == (640, 480)
            assert depth.mode in {"I", "I;16", "I;16L", "I;16B"}

        categories.update(item["category"] for item in label_by_rgb[rgb_name]["annotations"])

    assert len(categories) == 17
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    local_links = re.findall(r'(?:src|href)="((?:samples/|LICENSE)[^"]*)"', readme)
    missing = [link for link in local_links if not (ROOT / link).exists()]
    assert not missing, f"Broken local README links: {missing}"
    print(
        f"Validated {len(manifest)} RGB-D pairs, {len(categories)} categories, "
        f"and {len(local_links)} local README links."
    )


if __name__ == "__main__":
    main()
