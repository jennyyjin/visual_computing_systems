#!/usr/bin/env python3
"""Plot CogVideoX CPU-offload latency/memory tradeoff as an SVG."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PAIRS = [
    ("cogvideox_480x768_17f_15s", "17f, 480x768"),
    ("cogvideox_384x640_49f_15s", "49f, 384x640"),
    ("cogvideox_480x768_33f_15s", "33f, 480x768"),
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_row(rows: list[dict[str, str]], config_id: str) -> dict[str, str]:
    matches = [row for row in rows if row["config_id"] == config_id and row["prompt_id"] == "fast_action"]
    if not matches:
        raise ValueError(f"missing config: {config_id}")
    return matches[0]


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def write_svg(main_rows: list[dict[str, str]], no_offload_rows: list[dict[str, str]], out_path: Path) -> None:
    width, height = 1200, 700
    left, right, top, bottom = 96, 54, 86, 96
    plot_w = width - left - right
    plot_h = height - top - bottom

    pairs = []
    for config_id, label in PAIRS:
        offload = find_row(main_rows, config_id)
        no_offload = find_row(no_offload_rows, f"{config_id}_no_offload")
        pairs.append((label, offload, no_offload))

    memories = [as_float(row, "peak_memory_mb") / 1024 for _, a, b in pairs for row in (a, b)]
    latencies = [as_float(row, "latency_seconds") for _, a, b in pairs for row in (a, b)]
    x_min, x_max = min(memories) - 0.8, max(memories) + 0.8
    y_min, y_max = 0, max(latencies) + 4

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_h

    dark = "#111827"
    gray = "#6b7280"
    grid = "#e5e7eb"
    offload_color = "#2563eb"
    gpu_color = "#16a34a"
    line = "#94a3b8"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="44" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="{dark}">CPU offload trades latency for memory</text>',
    ]

    x_ticks = [11, 14, 17, 20]
    y_ticks = [0, 10, 20, 30]
    for tick in x_ticks:
        x = sx(tick)
        parts.extend(
            [
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" stroke="{grid}" stroke-width="1"/>',
                f'<text x="{x:.1f}" y="{height-bottom+28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#4b5563">{tick}</text>',
            ]
        )
    for tick in y_ticks:
        y = sy(tick)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>',
                f'<text x="{left-14}" y="{y+5:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="14" fill="#4b5563">{tick}</text>',
            ]
        )

    parts.extend(
        [
            f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="{dark}" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{width/2}" y="{height-28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="{dark}">Peak GPU memory (GB)</text>',
            f'<text x="30" y="{height/2}" text-anchor="middle" transform="rotate(-90 30 {height/2})" font-family="Arial, sans-serif" font-size="18" fill="{dark}">Latency (seconds)</text>',
        ]
    )

    label_offsets = [(-8, -28), (22, 32), (22, -28)]
    for index, (label, offload, no_offload) in enumerate(pairs):
        off_x = sx(as_float(offload, "peak_memory_mb") / 1024)
        off_y = sy(as_float(offload, "latency_seconds"))
        gpu_x = sx(as_float(no_offload, "peak_memory_mb") / 1024)
        gpu_y = sy(as_float(no_offload, "latency_seconds"))

        parts.append(
            f'<line x1="{off_x:.1f}" y1="{off_y:.1f}" x2="{gpu_x:.1f}" y2="{gpu_y:.1f}" stroke="{line}" stroke-width="3" stroke-dasharray="7 5"/>'
        )
        parts.append(f'<circle cx="{off_x:.1f}" cy="{off_y:.1f}" r="9" fill="{offload_color}" stroke="{dark}" stroke-width="2"/>')
        parts.append(f'<circle cx="{gpu_x:.1f}" cy="{gpu_y:.1f}" r="9" fill="{gpu_color}" stroke="{dark}" stroke-width="2"/>')
        label_dx, label_dy = label_offsets[index]
        label_x = gpu_x + label_dx
        label_y = gpu_y + label_dy
        label_w = len(label) * 7.2 + 16
        parts.extend(
            [
                f'<rect x="{label_x-8:.1f}" y="{label_y-17:.1f}" width="{label_w:.1f}" height="24" rx="5" fill="#ffffff" stroke="#cbd5e1" stroke-width="1"/>',
                f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-family="Arial, sans-serif" font-size="13" font-weight="600" fill="{gray}">{label}</text>',
            ]
        )

    legend_x, legend_y = left + 18, top + 18
    parts.extend(
        [
            f'<circle cx="{legend_x}" cy="{legend_y}" r="8" fill="{offload_color}" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{legend_x+18}" y="{legend_y+5}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">CPU offload</text>',
            f'<circle cx="{legend_x}" cy="{legend_y+30}" r="8" fill="{gpu_color}" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{legend_x+18}" y="{legend_y+35}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">No offload</text>',
        ]
    )

    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-metrics", type=Path, required=True)
    parser.add_argument("--no-offload-metrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_svg(load_rows(args.main_metrics), load_rows(args.no_offload_metrics), args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
