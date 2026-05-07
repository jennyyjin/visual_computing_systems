#!/usr/bin/env python3
"""
Score generated video frame directories and write per-run quality metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vscale.ppm import read_ppm


def pixel_stats(pixels: bytes) -> tuple[float, float]:
    avg = sum(pixels) / len(pixels)
    var = sum((value - avg) ** 2 for value in pixels) / len(pixels)
    return avg, math.sqrt(var)


def mean_abs_delta(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def sharpness_score(width: int, height: int, pixels: bytes) -> float:
    if width < 2 or height < 2:
        return 0.0
    total = 0.0
    count = 0
    for y in range(height):
        row = y * width * 3
        for x in range(1, width):
            idx = row + x * 3
            prev = idx - 3
            total += (
                abs(pixels[idx] - pixels[prev])
                + abs(pixels[idx + 1] - pixels[prev + 1])
                + abs(pixels[idx + 2] - pixels[prev + 2])
            ) / 3.0
            count += 1
    for y in range(1, height):
        row = y * width * 3
        prev_row = (y - 1) * width * 3
        for x in range(width):
            idx = row + x * 3
            prev = prev_row + x * 3
            total += (
                abs(pixels[idx] - pixels[prev])
                + abs(pixels[idx + 1] - pixels[prev + 1])
                + abs(pixels[idx + 2] - pixels[prev + 2])
            ) / 3.0
            count += 1
    return total / count


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def failure_reason(is_nonblank: bool, has_motion: bool, not_flicker_noise: bool) -> str:
    reasons = []
    if not is_nonblank:
        reasons.append("blank_or_low_contrast")
    if not has_motion:
        reasons.append("no_temporal_change")
    if not not_flicker_noise:
        reasons.append("random_flicker_noise")
    return "ok" if not reasons else "+".join(reasons)


def evaluate_run(run_dir: Path) -> dict:
    with (run_dir / "metadata.json").open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    frame_paths = sorted((run_dir / "frames").glob("*.ppm"))
    if not frame_paths:
        raise ValueError(f"no PPM frames found in {run_dir / 'frames'}")

    widths = []
    heights = []
    spatial_stds = []
    sharpness_values = []
    frame_bytes = []
    for frame_path in frame_paths:
        width, height, pixels = read_ppm(frame_path)
        widths.append(width)
        heights.append(height)
        frame_bytes.append(pixels)
        _, std = pixel_stats(pixels)
        spatial_stds.append(std)
        sharpness_values.append(sharpness_score(width, height, pixels))

    deltas = [
        mean_abs_delta(frame_bytes[i - 1], frame_bytes[i])
        for i in range(1, len(frame_bytes))
    ]

    spatial_std = mean(spatial_stds)
    sharpness = mean(sharpness_values)
    temporal_delta = mean(deltas) if deltas else 0.0
    max_delta = max(deltas) if deltas else 0.0
    min_delta = min(deltas) if deltas else 0.0

    nonblank_score = clamp01((spatial_std - 3.0) / 35.0)
    motion_score = clamp01(temporal_delta / 12.0)
    normalized_sharpness = clamp01(sharpness / 18.0)
    noise_penalty = clamp01((temporal_delta - 45.0) / 35.0)
    stability_score = 1.0 - noise_penalty
    quality_proxy = clamp01(
        nonblank_score
        * (0.45 + 0.35 * motion_score + 0.20 * normalized_sharpness)
        * stability_score
    )

    is_nonblank = spatial_std >= 5.0
    has_motion = temporal_delta >= 1.0
    not_flicker_noise = temporal_delta <= 80.0
    valid_video = is_nonblank and has_motion and not_flicker_noise

    config = metadata["config"]
    return {
        "run_id": metadata["run_id"],
        "model": metadata["model"],
        "prompt_id": metadata["prompt_id"],
        "config_id": config["config_id"],
        "steps": config["steps"],
        "width": widths[0],
        "height": heights[0],
        "frames": len(frame_paths),
        "precision": config.get("precision", ""),
        "latency_seconds": metadata["latency_seconds"],
        "peak_memory_mb": metadata.get("peak_memory_mb", ""),
        "spatial_std": round(spatial_std, 4),
        "temporal_delta": round(temporal_delta, 4),
        "sharpness_score": round(normalized_sharpness, 4),
        "min_temporal_delta": round(min_delta, 4),
        "max_temporal_delta": round(max_delta, 4),
        "nonblank_score": round(nonblank_score, 4),
        "motion_score": round(motion_score, 4),
        "stability_score": round(stability_score, 4),
        "quality_proxy": round(quality_proxy, 4),
        "valid_video": str(valid_video).lower(),
        "failure_reason": failure_reason(is_nonblank, has_motion, not_flicker_noise),
    }


def run_dirs_from_manifest(manifest_path: Path) -> list[Path]:
    with manifest_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Path(row["frames_dir"]).parent for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("outputs/runs"))
    parser.add_argument("--out", type=Path, default=Path("outputs/eval"))
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    run_dirs = (
        run_dirs_from_manifest(args.manifest)
        if args.manifest
        else [path for path in sorted(args.runs.iterdir()) if path.is_dir()]
    )
    rows = [evaluate_run(path) for path in run_dirs]
    rows.sort(key=lambda row: (row["model"], row["prompt_id"], float(row["latency_seconds"])))

    metrics_path = args.out / "metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    valid = sum(row["valid_video"] == "true" for row in rows)
    print(f"evaluated {len(rows)} runs ({valid} valid)")
    print(f"metrics: {metrics_path}")


if __name__ == "__main__":
    main()
