#!/usr/bin/env python3
"""Create a presentation SVG showing representative outputs for the three prompts."""

from __future__ import annotations

import argparse
import base64
import json
import struct
import textwrap
import zlib
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vscale.ppm import read_ppm


EXAMPLES = [
    {
        "title": "Static landscape",
        "summary": "Mountain lake at sunrise",
        "run_dir": Path("outputs_final/ltx_video/runs/ltx_static_landscape_ltx_fast_384x640_49f_20s"),
    },
    {
        "title": "Walking person",
        "summary": "Person crossing a city street",
        "run_dir": Path("outputs_final/ltx_video/runs/ltx_walking_person_ltx_fast_512x704_49f_20s"),
    },
    {
        "title": "Fast action",
        "summary": "Skateboarder kickflip",
        "run_dir": Path("outputs_final/ltx_video/runs/ltx_fast_action_ltx_fast_384x640_81f_20s"),
    },
]


def png_bytes(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    stride = width * 3
    rows = [b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(height)]
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(b"".join(rows), 9)),
            chunk(b"IEND", b""),
        ]
    )


def resize_nearest(width: int, height: int, pixels: bytes, target_width: int, target_height: int) -> bytes:
    out = bytearray(target_width * target_height * 3)
    for y in range(target_height):
        src_y = min(height - 1, int(y * height / target_height))
        for x in range(target_width):
            src_x = min(width - 1, int(x * width / target_width))
            src_idx = (src_y * width + src_x) * 3
            dst_idx = (y * target_width + x) * 3
            out[dst_idx : dst_idx + 3] = pixels[src_idx : src_idx + 3]
    return bytes(out)


def data_uri(frame_path: Path, width: int, height: int) -> str:
    src_width, src_height, pixels = read_ppm(frame_path)
    resized = resize_nearest(src_width, src_height, pixels, width, height)
    encoded = base64.b64encode(png_bytes(width, height, resized)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def frame_samples(frames_dir: Path) -> list[Path]:
    frames = sorted(frames_dir.glob("*.ppm"))
    if not frames:
        raise ValueError(f"no PPM frames found in {frames_dir}")
    indexes = [0, len(frames) // 2, len(frames) - 1]
    return [frames[index] for index in indexes]


def wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False)


def write_svg(out_path: Path) -> None:
    width, height = 1280, 620
    margin = 52
    gap = 28
    card_w = (width - 2 * margin - 2 * gap) / 3
    card_h = 530
    image_w = card_w - 44
    image_h = 100

    dark = "#111827"
    muted = "#4b5563"
    border = "#d1d5db"
    green = "#16a34a"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    for idx, example in enumerate(EXAMPLES):
        x = margin + idx * (card_w + gap)
        y = 44
        run_dir = example["run_dir"]
        with (run_dir / "metadata.json").open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        config = metadata["config"]
        prompt = metadata["prompt"]
        frames = frame_samples(run_dir / "frames")

        parts.extend(
            [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{card_w:.1f}" height="{card_h}" rx="12" fill="#f9fafb" stroke="{border}" stroke-width="1.5"/>',
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{card_w:.1f}" height="8" rx="4" fill="{green}"/>',
                f'<text x="{x+22:.1f}" y="{y+44:.1f}" font-family="Arial, sans-serif" font-size="25" font-weight="700" fill="{dark}">{example["title"]}</text>',
                f'<text x="{x+22:.1f}" y="{y+72:.1f}" font-family="Arial, sans-serif" font-size="16" fill="{muted}">{example["summary"]}</text>',
            ]
        )

        image_y = y + 100
        for frame_idx, frame_path in enumerate(frames):
            fy = image_y + frame_idx * (image_h + 12)
            parts.append(f'<rect x="{x+22:.1f}" y="{fy:.1f}" width="{image_w:.1f}" height="{image_h}" rx="5" fill="#e5e7eb"/>')
            parts.append(
                f'<image x="{x+22:.1f}" y="{fy:.1f}" width="{image_w:.1f}" height="{image_h}" preserveAspectRatio="xMidYMid slice" href="{data_uri(frame_path, int(image_w), image_h)}"/>'
            )

        details_y = y + 438
        details = f'{config["frames"]} frames, {config["steps"]} steps, {config["width"]}x{config["height"]}'
        parts.append(
            f'<text x="{x+22:.1f}" y="{details_y:.1f}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="{muted}">{details}</text>'
        )
        for line_idx, line in enumerate(wrap_lines(prompt, 44)[:2]):
            parts.append(
                f'<text x="{x+22:.1f}" y="{details_y+22+line_idx*18:.1f}" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">{line}</text>'
            )

    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("slides/assets/prompt_examples.svg"))
    args = parser.parse_args()
    write_svg(args.out)
    print(f"prompt examples: {args.out}")


if __name__ == "__main__":
    main()
