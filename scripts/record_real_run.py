#!/usr/bin/env python3
"""
Import externally generated frames into the shared V-Scale run schema.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def copy_frames(src: Path, dst: Path) -> int:
    frames = sorted(src.glob("*.ppm"))
    if not frames:
        raise ValueError(f"{src} does not contain .ppm frames")
    dst.mkdir(parents=True, exist_ok=True)
    for idx, frame in enumerate(frames):
        shutil.copy2(frame, dst / f"frame_{idx:04d}.ppm")
    return len(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a real model run using the V-Scale schema.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--precision", default="fp16")
    parser.add_argument("--guidance-scale", type=float, default=None)
    parser.add_argument("--offload-mode", default="")
    parser.add_argument("--latency-seconds", type=float, required=True)
    parser.add_argument("--peak-memory-mb", type=float, default=None)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("outputs/real"))
    args = parser.parse_args()

    run_dir = args.out / "runs" / args.run_id
    copied_frames = copy_frames(args.frames_dir, run_dir / "frames")
    if copied_frames != args.frames:
        print(f"warning: expected {args.frames} frames, copied {copied_frames}")

    config = {
        "config_id": f"steps{args.steps}_{args.width}x{args.height}_{args.frames}f",
        "steps": args.steps,
        "width": args.width,
        "height": args.height,
        "frames": copied_frames,
        "precision": args.precision,
        "guidance_scale": args.guidance_scale,
        "offload_mode": args.offload_mode,
    }
    metadata = {
        "run_id": args.run_id,
        "model": args.model,
        "prompt_id": args.prompt_id,
        "prompt": args.prompt,
        "config": config,
        "latency_seconds": round(args.latency_seconds, 6),
        "peak_memory_mb": "" if args.peak_memory_mb is None else args.peak_memory_mb,
        "output_format": "ppm_frame_directory",
        "frames_dir": str(run_dir / "frames"),
    }
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"recorded run: {run_dir}")
    print(f"frames copied: {copied_frames}")


if __name__ == "__main__":
    main()
