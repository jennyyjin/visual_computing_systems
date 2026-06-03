#!/usr/bin/env python3
"""Plot dominated configurations and the Pareto frontier as an SVG."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def is_dominated(row: dict[str, str], candidates: list[dict[str, str]]) -> bool:
    latency = as_float(row, "latency_seconds")
    quality = as_float(row, "quality_proxy")
    for other in candidates:
        if other["run_id"] == row["run_id"]:
            continue
        other_latency = as_float(other, "latency_seconds")
        other_quality = as_float(other, "quality_proxy")
        no_worse = other_latency <= latency and other_quality >= quality
        strictly_better = other_latency < latency or other_quality > quality
        if no_worse and strictly_better:
            return True
    return False


def load_metrics(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [row for row in rows if row.get("valid_video", "true") == "true"]


def nice_ticks(min_value: float, max_value: float, count: int = 6) -> list[float]:
    if min_value == max_value:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + i * step for i in range(count)]


def plot_svg(rows: list[dict[str, str]], out_path: Path) -> None:
    width = 1280
    height = 720
    margin_left = 96
    margin_right = 52
    margin_top = 82
    margin_bottom = 92
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    latencies = [as_float(row, "latency_seconds") for row in rows]
    qualities = [as_float(row, "quality_proxy") for row in rows]
    x_min, x_max = 0.0, max(latencies) * 1.05
    y_min, y_max = 0.0, 0.9

    def sx(value: float) -> float:
        return margin_left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value: float) -> float:
        return margin_top + (y_max - value) / (y_max - y_min) * plot_h

    frontier = [row for row in rows if not is_dominated(row, rows)]
    dominated = [row for row in rows if is_dominated(row, rows)]
    frontier.sort(key=lambda row: as_float(row, "latency_seconds"))

    green = "#15803d"
    orange = "#f59e0b"
    gray = "#6b7280"
    dark = "#111827"
    grid = "#e5e7eb"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{margin_left}" y="44" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="{dark}">Latency-quality tradeoff across profiled runs</text>',
        f'<text x="{margin_left}" y="70" font-family="Arial, sans-serif" font-size="16" fill="#4b5563">Gray points are dominated; green points trace the global Pareto frontier.</text>',
    ]

    for tick in nice_ticks(0, x_max, 6):
        x = sx(tick)
        parts.extend(
            [
                f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{height - margin_bottom}" stroke="{grid}" stroke-width="1"/>',
                f'<text x="{x:.1f}" y="{height - margin_bottom + 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#4b5563">{tick:.0f}</text>',
            ]
        )

    for tick in nice_ticks(0, y_max, 6):
        y = sy(tick)
        parts.extend(
            [
                f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>',
                f'<text x="{margin_left - 16}" y="{y + 5:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="14" fill="#4b5563">{tick:.2f}</text>',
            ]
        )

    parts.extend(
        [
            f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="{dark}" stroke-width="2"/>',
            f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{width / 2}" y="{height - 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="{dark}">Latency (seconds)</text>',
            f'<text x="30" y="{height / 2}" text-anchor="middle" transform="rotate(-90 30 {height / 2})" font-family="Arial, sans-serif" font-size="18" fill="{dark}">Quality proxy</text>',
        ]
    )

    frontier_points = " ".join(
        f'{sx(as_float(row, "latency_seconds")):.1f},{sy(as_float(row, "quality_proxy")):.1f}'
        for row in frontier
    )
    if frontier_points:
        parts.append(
            f'<polyline points="{frontier_points}" fill="none" stroke="{green}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    for row in dominated:
        x = sx(as_float(row, "latency_seconds"))
        y = sy(as_float(row, "quality_proxy"))
        shape = "triangle" if row["model"] == "cogvideox" else "circle"
        if shape == "triangle":
            points = f"{x:.1f},{y - 7:.1f} {x - 7:.1f},{y + 6:.1f} {x + 7:.1f},{y + 6:.1f}"
            parts.append(f'<polygon points="{points}" fill="{gray}" opacity="0.78"/>')
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{gray}" opacity="0.78"/>')

    for row in frontier:
        x = sx(as_float(row, "latency_seconds"))
        y = sy(as_float(row, "quality_proxy"))
        fill = green if row["model"] == "ltx" else orange
        shape = "triangle" if row["model"] == "cogvideox" else "circle"
        if shape == "triangle":
            points = f"{x:.1f},{y - 10:.1f} {x - 10:.1f},{y + 8:.1f} {x + 10:.1f},{y + 8:.1f}"
            parts.append(f'<polygon points="{points}" fill="{fill}" stroke="{dark}" stroke-width="2"/>')
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{fill}" stroke="{dark}" stroke-width="2"/>')

    legend_x = width - margin_right - 176
    legend_y = margin_top + 22
    parts.extend(
        [
            f'<rect x="{legend_x - 18}" y="{legend_y - 22}" width="176" height="132" rx="8" fill="#ffffff" opacity="0.92" stroke="#e5e7eb" stroke-width="1"/>',
            f'<circle cx="{legend_x}" cy="{legend_y}" r="7" fill="{gray}" opacity="0.78"/>',
            f'<text x="{legend_x + 18}" y="{legend_y + 5}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">Dominated configs</text>',
            f'<circle cx="{legend_x}" cy="{legend_y + 30}" r="8" fill="{green}" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{legend_x + 18}" y="{legend_y + 35}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">Pareto frontier</text>',
            f'<circle cx="{legend_x}" cy="{legend_y + 62}" r="7" fill="#ffffff" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{legend_x + 18}" y="{legend_y + 67}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">LTX-Video</text>',
            f'<polygon points="{legend_x},{legend_y + 84} {legend_x - 8},{legend_y + 98} {legend_x + 8},{legend_y + 98}" fill="#ffffff" stroke="{dark}" stroke-width="2"/>',
            f'<text x="{legend_x + 18}" y="{legend_y + 99}" font-family="Arial, sans-serif" font-size="15" fill="{dark}">CogVideoX</text>',
        ]
    )

    parts.append(
        f'<text x="{margin_left}" y="{height - 10}" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">Global frontier shown across all valid runs; prompt-specific scheduling can still select CogVideoX for high-budget fast-action prompts.</text>'
    )
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = load_metrics(args.metrics)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    plot_svg(rows, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
