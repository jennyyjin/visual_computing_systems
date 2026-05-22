#!/usr/bin/env python3
"""Run real video-generation sweeps on Modal GPUs and import outputs locally."""

from __future__ import annotations

import argparse
import csv
import io
import json
import tarfile
from collections import defaultdict
from pathlib import Path


try:
    import modal
except ImportError as exc:
    raise SystemExit(
        "Missing Modal. Install and authenticate with:\n"
        "  python3 -m pip install modal\n"
        "  modal setup"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
REMOTE_SRC = "/root/vscale_src"
HF_CACHE = "/cache/huggingface"


image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "accelerate>=1.1.0",
        "diffusers[torch]>=0.35.0",
        "hf_transfer>=0.1.8",
        "imageio>=2.35.0",
        "imageio-ffmpeg>=0.5.1",
        "pillow>=10.4.0",
        "sentencepiece>=0.2.0",
        "torch>=2.5.0",
        "transformers>=4.46.0",
    )
    .env(
        {
            "HF_HOME": HF_CACHE,
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
    .add_local_dir(str(REPO_ROOT / "src"), remote_path=REMOTE_SRC)
)

app = modal.App("vscale-video-sweep", image=image)
hf_cache = modal.Volume.from_name("vscale-hf-cache", create_if_missing=True)


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict) -> None:
    backend = config["backend"]
    width = int(config["width"])
    height = int(config["height"])
    frames = int(config["frames"])
    if width % 16 != 0 or height % 16 != 0:
        raise ValueError(f"{config['config_id']} width/height must be divisible by 16")
    if backend == "cogvideox" and frames % 4 != 1:
        raise ValueError(f"{config['config_id']} CogVideoX frames should be 4k+1, e.g. 49 or 81")
    if backend == "ltx" and frames % 8 != 1:
        raise ValueError(f"{config['config_id']} LTX frames should be 8k+1, e.g. 49 or 81")


def selected_prompts(prompts: list[dict], prompt_ids: set[str] | None) -> list[dict]:
    if prompt_ids is None:
        return prompts
    return [prompt for prompt in prompts if prompt["id"] in prompt_ids]


def selected_configs(configs: list[dict], backend: str | None, config_ids: set[str] | None) -> list[dict]:
    rows = configs
    if backend:
        rows = [config for config in rows if config["backend"] == backend]
    if config_ids:
        rows = [config for config in rows if config["config_id"] in config_ids]
    for config in rows:
        validate_config(config)
    return rows


def build_specs(prompts: list[dict], configs: list[dict], seed: int) -> list[dict]:
    specs = []
    for prompt in prompts:
        for config in configs:
            specs.append(
                {
                    "run_id": f"{config['backend']}_{prompt['id']}_{config['config_id']}",
                    "prompt_id": prompt["id"],
                    "prompt": prompt["prompt"],
                    "negative_prompt": prompt.get("negative_prompt", ""),
                    "seed": seed,
                    **config,
                }
            )
    return specs


def skip_completed_specs(specs: list[dict], out: Path) -> list[dict]:
    pending = []
    for spec in specs:
        run_dir = out / "runs" / spec["run_id"]
        if (run_dir / "metadata.json").exists() and (run_dir / "video.mp4").exists():
            print(f"skipping existing run: {spec['run_id']}")
            continue
        pending.append(spec)
    return pending


def chunks(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[start : start + size] for start in range(0, len(rows), size)]


def write_manifest(out: Path) -> None:
    rows = []
    for metadata_path in sorted((out / "runs").glob("*/metadata.json")):
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        rows.append(
            {
                "run_id": metadata["run_id"],
                "model": metadata["model"],
                "prompt_id": metadata["prompt_id"],
                "latency_seconds": metadata["latency_seconds"],
                "wall_clock_generation_seconds": metadata.get("wall_clock_generation_seconds", ""),
                "peak_memory_mb": metadata.get("peak_memory_mb", ""),
                "frames_dir": str(metadata_path.parent / "frames"),
            }
        )
    if not rows:
        return
    manifest_path = out / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def extract_runs(archive: bytes, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        safe_members = []
        for member in tar.getmembers():
            target = (out / member.name).resolve()
            if not str(target).startswith(str(out.resolve())):
                raise RuntimeError(f"unsafe tar member: {member.name}")
            safe_members.append(member)
        tar.extractall(out, members=safe_members)


def rewrite_imported_paths(out: Path) -> None:
    for metadata_path in sorted((out / "runs").glob("*/metadata.json")):
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["frames_dir"] = str(metadata_path.parent / "frames")
        video_path = metadata_path.parent / "video.mp4"
        if video_path.exists():
            metadata["video_path"] = str(video_path)
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)


@app.function(gpu="L40S", timeout=60 * 60, volumes={"/cache": hf_cache})
def run_remote_batch(specs: list[dict]) -> bytes:
    import sys
    import tempfile
    import time
    from pathlib import Path

    import torch
    from diffusers.utils import export_to_video

    sys.path.insert(0, REMOTE_SRC)
    from vscale.ppm import write_ppm

    def dtype_from_spec(spec: dict):
        precision = spec.get("precision", "fp16")
        if precision == "bf16" and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16

    def load_pipeline(spec: dict):
        backend = spec["backend"]
        dtype = dtype_from_spec(spec)
        start = time.perf_counter()
        if backend == "cogvideox":
            from diffusers import CogVideoXPipeline

            pipe = CogVideoXPipeline.from_pretrained(
                spec["model_id"],
                torch_dtype=dtype,
                cache_dir=HF_CACHE,
            )
        elif backend == "ltx":
            from diffusers import LTXPipeline

            pipe = LTXPipeline.from_pretrained(
                spec["model_id"],
                torch_dtype=dtype,
                cache_dir=HF_CACHE,
            )
        else:
            raise ValueError(f"unsupported backend: {backend}")

        if spec.get("offload_mode") == "model_cpu_offload":
            pipe.enable_model_cpu_offload()
        else:
            pipe.to("cuda")
        if hasattr(pipe, "vae"):
            if hasattr(pipe.vae, "enable_tiling"):
                pipe.vae.enable_tiling()
            if hasattr(pipe.vae, "enable_slicing"):
                pipe.vae.enable_slicing()
        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=True)
        return pipe, dtype, time.perf_counter() - start

    def generate(pipe, spec: dict):
        generator = torch.Generator(device="cuda").manual_seed(int(spec["seed"]))
        kwargs = {
            "prompt": spec["prompt"],
            "negative_prompt": spec.get("negative_prompt") or None,
            "num_inference_steps": int(spec["steps"]),
            "num_frames": int(spec["frames"]),
            "height": int(spec["height"]),
            "width": int(spec["width"]),
            "guidance_scale": float(spec["guidance_scale"]),
            "generator": generator,
        }
        if spec["backend"] == "ltx":
            kwargs["decode_timestep"] = spec.get("decode_timestep", 0.03)
            kwargs["decode_noise_scale"] = spec.get("decode_noise_scale", 0.025)
        return pipe(**kwargs).frames[0]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pipe = None
        dtype = None
        load_seconds = None
        for spec in specs:
            if pipe is None:
                pipe, dtype, load_seconds = load_pipeline(spec)

            run_dir = root / "runs" / spec["run_id"]
            frames_dir = run_dir / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()

            start = time.perf_counter()
            frames = generate(pipe, spec)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            latency = time.perf_counter() - start
            peak_memory_mb = ""
            if torch.cuda.is_available():
                peak_memory_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)

            for idx, frame in enumerate(frames):
                image = frame.convert("RGB")
                write_ppm(frames_dir / f"frame_{idx:04d}.ppm", image.width, image.height, image.tobytes())

            video_path = run_dir / "video.mp4"
            export_to_video(frames, str(video_path), fps=int(spec["fps"]))

            metadata = {
                "run_id": spec["run_id"],
                "model": spec["backend"],
                "model_id": spec["model_id"],
                "prompt_id": spec["prompt_id"],
                "prompt": spec["prompt"],
                "negative_prompt": spec.get("negative_prompt", ""),
                "seed": spec["seed"],
                "config": {
                    "config_id": spec["config_id"],
                    "steps": int(spec["steps"]),
                    "width": frames[0].width,
                    "height": frames[0].height,
                    "frames": len(frames),
                    "precision": str(dtype).replace("torch.", ""),
                    "guidance_scale": float(spec["guidance_scale"]),
                    "offload_mode": spec.get("offload_mode", ""),
                    "fps": int(spec["fps"]),
                },
                "latency_seconds": round(latency, 6),
                "model_load_seconds": round(load_seconds or 0.0, 6),
                "peak_memory_mb": peak_memory_mb,
                "output_format": "ppm_frame_directory",
                "video_path": str(video_path),
                "frames_dir": str(frames_dir),
            }
            with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(root / "runs", arcname="runs")
        return buffer.getvalue()


@app.local_entrypoint()
def main(
    prompts: str = "configs/prompts.json",
    sweep: str = "configs/modal_sweep.json",
    out: str = "outputs/ltx_video",
    backend: str | None = "ltx",
    prompt_id: str | None = None,
    config_id: str | None = None,
    seed: int = 1234,
    batch_size: int = 1,
    skip_existing: bool = True,
) -> None:
    prompt_ids = set(prompt_id.split(",")) if prompt_id else None
    config_ids = set(config_id.split(",")) if config_id else None
    prompt_rows = selected_prompts(load_json(Path(prompts)), prompt_ids)
    config_rows = selected_configs(load_json(Path(sweep)), backend, config_ids)
    out_path = Path(out)
    specs = build_specs(prompt_rows, config_rows, seed)
    if skip_existing:
        specs = skip_completed_specs(specs, out_path)
    if not specs:
        raise SystemExit("no Modal run specs selected")
    if batch_size < 1:
        raise SystemExit("batch_size must be at least 1")

    groups = defaultdict(list)
    for spec in specs:
        groups[(spec["backend"], spec["model_id"], spec["precision"], spec["offload_mode"])].append(spec)

    print(f"selected {len(specs)} runs across {len(groups)} model group(s)")
    for key, batch in groups.items():
        backend_name, model_id, precision, offload = key
        print(f"running {len(batch)} {backend_name} run(s): {model_id}, {precision}, {offload}")
        for index, sub_batch in enumerate(chunks(batch, batch_size), start=1):
            print(f"  chunk {index}: {len(sub_batch)} run(s)")
            archive = run_remote_batch.remote(sub_batch)
            extract_runs(archive, out_path)
            rewrite_imported_paths(out_path)
    write_manifest(out_path)
    print(f"outputs: {out_path / 'runs'}")
    print(f"manifest: {out_path / 'manifest.csv'}")
