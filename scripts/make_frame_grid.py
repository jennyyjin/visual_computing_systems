#!/usr/bin/env python3
"""Create a lightweight SVG frame grid from selected output runs."""

from __future__ import annotations

import argparse
import base64
import struct
import zlib
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vscale.ppm import read_ppm


DEFAULT_RUNS = [
    "white_fast_action_tiny_preview",
    "static_frame_fast_action_tiny_preview",
    "noise_fast_action_tiny_preview",
    "moving_square_fast_action_tiny_preview",
]


def auto_run_ids(runs_root: Path) -> list[str]:
    return [path.name for path in sorted(runs_root.iterdir()) if (path / "frames").is_dir()]


def png_bytes(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = []
    stride = width * 3
    for y in range(height):
        rows.append(b"\x00" + pixels[y * stride : (y + 1) * stride])
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


def write_frame_grid(runs_root: Path, run_ids: list[str], out_path: Path) -> None:
    thumb_w = 180
    thumb_h = 120
    label_w = 250
    gap = 16
    row_h = thumb_h + 42
    margin = 24
    width = margin * 2 + label_w + gap + 3 * thumb_w + 2 * gap
    height = margin * 2 + 34 + row_h * len(run_ids)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="32" font-family="Arial, sans-serif" font-size="20" font-weight="700">Generated Video Frame Samples</text>',
        '<text x="290" y="62" font-family="Arial, sans-serif" font-size="12" fill="#555">first frame</text>',
        '<text x="486" y="62" font-family="Arial, sans-serif" font-size="12" fill="#555">middle frame</text>',
        '<text x="682" y="62" font-family="Arial, sans-serif" font-size="12" fill="#555">last frame</text>',
    ]

    start_y = margin + 52
    for row, run_id in enumerate(run_ids):
        y = start_y + row * row_h
        frames = frame_samples(runs_root / run_id / "frames")
        label = run_id.replace("_fast_action_tiny_preview", "").replace("_", " ")
        svg.append(f'<text x="{margin}" y="{y + 34}" font-family="Arial, sans-serif" font-size="15" font-weight="700">{label}</text>')
        svg.append(f'<text x="{margin}" y="{y + 56}" font-family="Arial, sans-serif" font-size="12" fill="#666">{run_id}</text>')
        for col, frame_path in enumerate(frames):
            x = margin + label_w + gap + col * (thumb_w + gap)
            svg.append(f'<rect x="{x - 1}" y="{y - 1}" width="{thumb_w + 2}" height="{thumb_h + 2}" fill="#ddd"/>')
            svg.append(f'<image x="{x}" y="{y}" width="{thumb_w}" height="{thumb_h}" href="{data_uri(frame_path, thumb_w, thumb_h)}"/>')

    svg.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an SVG frame grid from selected V-Scale runs.")
    parser.add_argument("--runs", type=Path, default=Path("outputs_final/runs"))
    parser.add_argument("--out", type=Path, default=Path("analysis/frame_grid.svg"))
    parser.add_argument("--run-id", action="append", dest="run_ids", default=None)
    args = parser.parse_args()
    run_ids = args.run_ids or auto_run_ids(args.runs) or DEFAULT_RUNS
    write_frame_grid(args.runs, run_ids, args.out)
    print(f"frame grid: {args.out}")


if __name__ == "__main__":
    main()
