#!/usr/bin/env python3
"""
Run CogVideoX-2B through Diffusers and export results for V-Scale evaluation.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vscale.ppm import write_ppm


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CogVideoX-2B runner. Requires torch, diffusers, transformers, accelerate, and imageio/ffmpeg support."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--prompt-id", default="manual")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--width", type=int, default=360)
    parser.add_argument("--guidance-scale", type=float, default=6.0)
    parser.add_argument("--model-id", default="THUDM/CogVideoX-2b")
    parser.add_argument("--out", type=Path, default=Path("outputs/cogvideox"))
    args = parser.parse_args()

    try:
        import torch
        from diffusers import CogVideoXPipeline
        from diffusers.utils import export_to_video
    except ImportError as exc:
        raise SystemExit(
            "Missing dependencies."
        ) from exc

    run_dir = args.out / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    pipe = CogVideoXPipeline.from_pretrained(args.model_id, torch_dtype=dtype)
    if torch.cuda.is_available():
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        pipe.vae.enable_slicing()
        torch.cuda.reset_peak_memory_stats()
    else:
        pipe.enable_model_cpu_offload()

    start = time.perf_counter()
    result = pipe(
        prompt=args.prompt,
        num_videos_per_prompt=1,
        num_inference_steps=args.steps,
        num_frames=args.frames,
        height=args.height,
        width=args.width,
        guidance_scale=args.guidance_scale,
    )
    latency = time.perf_counter() - start
    peak_memory_mb = ""
    if torch.cuda.is_available():
        peak_memory_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)

    frames_dir = run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = result.frames[0]
    for idx, frame in enumerate(frames):
        image = frame.convert("RGB")
        write_ppm(frames_dir / f"frame_{idx:04d}.ppm", image.width, image.height, image.tobytes())

    video_path = run_dir / "video.mp4"
    export_to_video(result.frames[0], str(video_path), fps=8)
    width = frames[0].width if frames else ""
    height = frames[0].height if frames else ""

    metadata = {
        "run_id": args.run_id,
        "model": "cogvideox-2b",
        "prompt_id": args.prompt_id,
        "prompt": args.prompt,
        "config": {
            "config_id": f"steps{args.steps}_{args.frames}f",
            "steps": args.steps,
            "width": width,
            "height": height,
            "frames": len(frames),
            "precision": str(dtype).replace("torch.", ""),
            "guidance_scale": args.guidance_scale,
            "offload_mode": "model_cpu_offload",
        },
        "latency_seconds": round(latency, 6),
        "peak_memory_mb": peak_memory_mb,
        "output_format": "ppm_frame_directory",
        "video_path": str(video_path),
        "frames_dir": str(frames_dir),
    }
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"generated video: {video_path}")
    print(f"frames: {frames_dir}")
    print(f"latency_seconds: {latency:.3f}")


if __name__ == "__main__":
    main()
