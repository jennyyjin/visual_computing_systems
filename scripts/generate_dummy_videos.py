#!/usr/bin/env python3
"""
Generate dummy video baselines for testing the V-Scale evaluation pipeline.
Baselines include white frames, black frames, static frame, noise, and a moving square.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vscale.ppm import write_ppm


BASELINES = ("white", "black", "static_frame", "noise", "moving_square")


def load_json(file_path: Path):
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def empty_frame(width: int, height: int, frame_idx: int, frames: int) -> bytes:
    return bytes([255, 255, 255]) * width * height


def black_frame(width: int, height: int, frame_idx: int, frames: int) -> bytes:
    return bytes([0, 0, 0]) * width * height


def static_frame(width: int, height: int, frame_idx: int, frames: int) -> bytes:
    pixels = bytearray([236, 239, 244] * width * height)
    square = max(10, min(width, height) // 4)
    x0 = width // 2 - square // 2
    y0 = height // 2 - square // 2
    for y in range(max(0, y0), min(height, y0 + square)):
        for x in range(max(0, x0), min(width, x0 + square)):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes([210, 42, 64])
    return bytes(pixels)


def noise_frame(width: int, height: int, frame_idx: int, frames: int) -> bytes:
    rng = random.Random(1009 + frame_idx)
    return bytes(rng.randrange(0, 256) for _ in range(width * height * 3))


def moving_square_frame(width: int, height: int, frame_idx: int, frames: int) -> bytes:
    pixels = bytearray([236, 239, 244] * width * height)
    square = max(10, min(width, height) // 5)
    span = max(1, width - square)
    x0 = int(span * frame_idx / max(1, frames - 1))
    y0 = height // 2 - square // 2
    for y in range(max(0, y0), min(height, y0 + square)):
        for x in range(max(0, x0), min(width, x0 + square)):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes([210, 42, 64])
    return bytes(pixels)


FRAME_GENERATORS = {
    "white": empty_frame,
    "black": black_frame,
    "static_frame": static_frame,
    "noise": noise_frame,
    "moving_square": moving_square_frame,
}


def generate_run(out_dir: Path, prompt: dict, config: dict, baseline: str) -> dict:
    run_id = f"{baseline}_{prompt['id']}_{config['config_id']}"
    run_dir = out_dir / "runs" / run_id
    frames_dir = run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    width = int(config["width"])
    height = int(config["height"])
    frames = int(config["frames"])
    steps = int(config["steps"])
    generator = FRAME_GENERATORS[baseline]

    start = time.perf_counter()
    for frame_idx in range(frames):
        pixels = generator(width, height, frame_idx, frames)
        write_ppm(frames_dir / f"frame_{frame_idx:04d}.ppm", width, height, pixels)
    elapsed = time.perf_counter() - start

    simulated_latency = {
        "white": 0.02,
        "black": 0.02,
        "static_frame": 0.03,
        "noise": 0.04,
        "moving_square": 0.06,
    }[baseline]
    simulated_latency += 0.0000015 * width * height * frames * max(1, steps) / 4

    metadata = {
        "run_id": run_id,
        "model": baseline,
        "prompt_id": prompt["id"],
        "prompt": prompt["prompt"],
        "config": config,
        "latency_seconds": round(simulated_latency, 6),
        "wall_clock_generation_seconds": round(elapsed, 6),
        "peak_memory_mb": "",
        "output_format": "ppm_frame_directory",
        "frames_dir": str(frames_dir),
    }
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--prompts", type=Path, default=Path("configs/prompts.json"))
    parser.add_argument("--sweep", type=Path, default=Path("configs/sweep.json"))
    args = parser.parse_args()

    prompts = load_json(args.prompts)
    sweep = load_json(args.sweep)
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for prompt in prompts:
        for config in sweep:
            for baseline in BASELINES:
                rows.append(generate_run(args.out, prompt, config, baseline))

    manifest_path = args.out / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "model",
                "prompt_id",
                "latency_seconds",
                "wall_clock_generation_seconds",
                "peak_memory_mb",
                "frames_dir",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})

    print(f"generated {len(rows)} runs")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
