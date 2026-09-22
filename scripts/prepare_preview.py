"""Build a compact, representative AquaSpatial preview release.

The script expects the private source dataset to contain label.json, sft.json,
rgb/, and depth_16bit/. It writes only the selected preview records and paired
images into this repository.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_RE = re.compile(r"navigate to (?:a|an) (.+?)\.", re.IGNORECASE)
DOMAIN_QUOTAS = {"artificial_pool": 32, "outdoor_lakes": 8}
CASE_TARGETS = {
    "artificial_pool": {
        "target_and_obstacle": 13,
        "target_only": 8,
        "obstacle_only": 8,
        "empty": 3,
    },
    "outdoor_lakes": {
        "target_and_obstacle": 3,
        "target_only": 2,
        "obstacle_only": 2,
        "empty": 1,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    return parser.parse_args()


def locate_depth_dir(source_root: Path) -> Path:
    candidates = [
        source_root / "depth_16bit",
        source_root / "depth_16bit" / "depth_16bit",
    ]
    for candidate in candidates:
        if (candidate / "depth_000001.png").is_file():
            return candidate
    raise FileNotFoundError("Could not locate depth_000001.png under depth_16bit/")


def extract_target(sample: dict) -> str:
    prompt = next(
        message.get("value", "")
        for message in sample.get("conversations", [])
        if message.get("from") == "human"
    )
    match = TARGET_RE.search(prompt)
    if not match:
        raise ValueError(f"Could not parse target from prompt: {prompt!r}")
    return match.group(1).strip().lower()


def response_case(target: str, annotations: list[dict]) -> str:
    has_target = any(item["category"] == target for item in annotations)
    has_obstacle = any(item["category"] != target for item in annotations)
    if has_target and has_obstacle:
        return "target_and_obstacle"
    if has_target:
        return "target_only"
    if has_obstacle:
        return "obstacle_only"
    return "empty"


def scene_quality(scene: dict) -> float:
    annotations = scene["label"].get("annotations", [])
    if not annotations:
        return 0.0

    center_penalty = 0.0
    edge_penalty = 0.0
    distance_penalty = 0.0
    for item in annotations:
        x1, y1, x2, y2 = item["bbox"]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        center_penalty += abs(cx - 320) / 320 + abs(cy - 240) / 240
        edge_penalty += int(x1 <= 2 or y1 <= 2 or x2 >= 638 or y2 >= 478)
        distance = item.get("distance_m")
        if distance is None or distance < 0.6 or distance > 5.0:
            distance_penalty += 1.0

    count = len(annotations)
    return -center_penalty / count - 1.5 * edge_penalty - distance_penalty + min(count, 4) * 0.08


def feature_tokens(scene: dict) -> set[str]:
    categories = {item["category"] for item in scene["label"].get("annotations", [])}
    count = len(scene["label"].get("annotations", []))
    return (
        {f"category:{category}" for category in categories}
        | {f"case:{scene['case']}"}
        | {f"object_count:{count}"}
    )


def choose_domain(candidates: list[dict], domain: str, quota: int) -> list[dict]:
    all_tokens = set().union(*(feature_tokens(scene) for scene in candidates))
    selected: list[dict] = []
    selected_ids: set[int] = set()
    uncovered = set(all_tokens)

    while uncovered and len(selected) < quota:
        scene = max(
            (item for item in candidates if item["scene_id"] not in selected_ids),
            key=lambda item: (
                len(feature_tokens(item) & uncovered),
                scene_quality(item),
                -item["scene_id"],
            ),
        )
        selected.append(scene)
        selected_ids.add(scene["scene_id"])
        uncovered -= feature_tokens(scene)

    desired = CASE_TARGETS[domain]
    while len(selected) < quota:
        current = Counter(item["case"] for item in selected)
        deficits = {case: desired[case] - current[case] for case in desired}
        needed_case = max(deficits, key=lambda case: (deficits[case], case))
        pool = [
            item
            for item in candidates
            if item["scene_id"] not in selected_ids and item["case"] == needed_case
        ]
        if not pool or deficits[needed_case] <= 0:
            pool = [item for item in candidates if item["scene_id"] not in selected_ids]

        def diversity(item: dict) -> float:
            nearest = min(abs(item["scene_id"] - chosen["scene_id"]) for chosen in selected)
            return nearest / 500.0 + scene_quality(item)

        scene = max(pool, key=lambda item: (diversity(item), -item["scene_id"]))
        selected.append(scene)
        selected_ids.add(scene["scene_id"])

    if uncovered:
        raise RuntimeError(f"Preview quota for {domain} could not cover: {sorted(uncovered)}")
    return selected


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_flat_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    depth_dir = locate_depth_dir(source_root)
    labels = json.loads((source_root / "label.json").read_text(encoding="utf-8"))
    sft = json.loads((source_root / "sft.json").read_text(encoding="utf-8"))
    if len(labels) != 5000 or len(sft) != 5000:
        raise ValueError("Expected 5,000 aligned label and SFT records")

    scenes = []
    for scene_id, (label, sample) in enumerate(zip(labels, sft), start=1):
        expected_rgb = f"rgb_{scene_id:06d}.jpg"
        expected_depth = f"depth_{scene_id:06d}.png"
        if label.get("images_name") != [expected_rgb, expected_depth]:
            raise ValueError(f"Unexpected label image alignment at scene {scene_id}")
        target = extract_target(sample)
        domain = "artificial_pool" if scene_id <= 4000 else "outdoor_lakes"
        scenes.append(
            {
                "scene_id": scene_id,
                "domain": domain,
                "target": target,
                "case": response_case(target, label.get("annotations", [])),
                "label": label,
                "sft": sample,
            }
        )

    selected = []
    for domain, quota in DOMAIN_QUOTAS.items():
        selected.extend(choose_domain([scene for scene in scenes if scene["domain"] == domain], domain, quota))
    selected.sort(key=lambda item: item["scene_id"])

    samples_dir = REPO_ROOT / "samples"
    rgb_out = samples_dir / "rgb"
    depth_out = samples_dir / "depth_16bit"
    clear_flat_directory(rgb_out)
    clear_flat_directory(depth_out)

    subset_labels = []
    subset_sft = []
    manifest_rows = []
    for scene in selected:
        scene_id = scene["scene_id"]
        rgb_name = f"rgb_{scene_id:06d}.jpg"
        depth_name = f"depth_{scene_id:06d}.png"
        rgb_source = source_root / "rgb" / rgb_name
        depth_source = depth_dir / depth_name
        rgb_target = rgb_out / rgb_name
        depth_target = depth_out / depth_name
        shutil.copy2(rgb_source, rgb_target)
        shutil.copy2(depth_source, depth_target)

        with Image.open(rgb_target) as rgb_image, Image.open(depth_target) as depth_image:
            if rgb_image.size != depth_image.size:
                raise ValueError(f"RGB/depth size mismatch for scene {scene_id}")
            if depth_image.mode not in {"I", "I;16", "I;16L", "I;16B"}:
                raise ValueError(f"Depth image is not 16-bit for scene {scene_id}: {depth_image.mode}")
            width, height = rgb_image.size

        subset_labels.append(scene["label"])
        portable_sft = json.loads(json.dumps(scene["sft"]))
        portable_sft["images"] = [
            f"samples/rgb/{rgb_name}",
            f"samples/depth_16bit/{depth_name}",
        ]
        subset_sft.append(portable_sft)
        categories = sorted({item["category"] for item in scene["label"].get("annotations", [])})
        manifest_rows.append(
            {
                "scene_id": scene_id,
                "domain": scene["domain"],
                "rgb_path": portable_sft["images"][0],
                "depth_path": portable_sft["images"][1],
                "width": width,
                "height": height,
                "object_count": len(scene["label"].get("annotations", [])),
                "categories": "|".join(categories),
                "instruction_target": scene["target"],
                "response_case": scene["case"],
                "rgb_sha256": sha256(rgb_target),
                "depth_sha256": sha256(depth_target),
            }
        )

    (samples_dir / "label_sample.json").write_text(
        json.dumps(subset_labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (samples_dir / "sft_sample.json").write_text(
        json.dumps(subset_sft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (samples_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    categories = sorted({category for row in manifest_rows for category in row["categories"].split("|") if category})
    print(f"Wrote {len(selected)} RGB-D pairs ({Counter(row['domain'] for row in manifest_rows)})")
    print(f"Covered {len(categories)} categories: {', '.join(categories)}")
    print(f"Response cases: {Counter(row['response_case'] for row in manifest_rows)}")
    print("Scene IDs:", ", ".join(str(scene["scene_id"]) for scene in selected))


if __name__ == "__main__":
    main()
