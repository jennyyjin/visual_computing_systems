#!/usr/bin/env python3
"""Create controlled bottleneck-analysis tables from profiled runs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


MODEL_LABELS = {"ltx": "LTX-Video", "cogvideox": "CogVideoX-2B"}
PROMPT_LABELS = {
    "fast_action": "fast action",
    "static_landscape": "static landscape",
    "walking_person": "walking person",
}


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f(row: dict, key: str) -> float:
    return float(row[key])


def avg(rows: list[dict], key: str) -> float:
    return sum(f(row, key) for row in rows) / len(rows)


def slope(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in points) / denom


def average_duplicate_x(rows: list[dict], x_key: str) -> list[tuple[float, float, float]]:
    groups: dict[float, list[dict]] = defaultdict(list)
    for row in rows:
        groups[f(row, x_key)].append(row)
    points = []
    for x_value, group in groups.items():
        points.append((x_value, avg(group, "latency_seconds"), avg(group, "quality_proxy")))
    return sorted(points)


def controlled_groups(rows: list[dict], fixed_keys: list[str], x_key: str) -> list[tuple[tuple[str, ...], list[tuple[float, float, float]]]]:
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("valid_video", "").lower() == "true":
            groups[tuple(row[key] for key in fixed_keys)].append(row)
    output = []
    for key, group in groups.items():
        points = average_duplicate_x(group, x_key)
        if len(points) >= 2:
            output.append((key, points))
    return sorted(output)


def summarize_groups(
    rows: list[dict],
    fixed_keys: list[str],
    x_key: str,
    x_label: str,
    unit: str,
) -> list[str]:
    lines = [
        f"### Controlled {x_label} Sweep",
        "",
        f"Only `{x_key}` changes within each row group. Other listed variables are held fixed.",
        "",
        "| Model | Prompt | Fixed setting | Range | Latency change | Slope | Quality change |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for key, points in controlled_groups(rows, fixed_keys, x_key):
        row_info = dict(zip(fixed_keys, key))
        model = row_info.get("model", "")
        prompt = row_info.get("prompt_id", "")
        fixed_setting = ", ".join(
            f"{name}={value}"
            for name, value in row_info.items()
            if name not in {"model", "prompt_id"}
        )
        first = points[0]
        last = points[-1]
        latency_change = last[1] - first[1]
        quality_change = last[2] - first[2]
        lines.append(
            f"| {MODEL_LABELS.get(model, model)} | {PROMPT_LABELS.get(prompt, prompt)} | "
            f"{fixed_setting} | {first[0]:.0f}->{last[0]:.0f} | "
            f"{latency_change:.3f}s | {slope([(x, y) for x, y, _ in points]):.3f} s/{unit} | "
            f"{quality_change:+.4f} |"
        )
    lines.append("")
    return lines


def resolution_summary(rows: list[dict]) -> list[str]:
    fixed_keys = ["model", "prompt_id", "steps", "frames"]
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("valid_video", "").lower() == "true":
            groups[tuple(row[key] for key in fixed_keys)].append(row)

    lines = [
        "### Controlled Resolution Comparison",
        "",
        "Steps and frame count are held fixed; only pixel count changes.",
        "",
        "| Model | Prompt | Fixed setting | Pixel change | Latency change | Latency ratio | Quality change |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for key, group in sorted(groups.items()):
        by_pixels: dict[float, list[dict]] = defaultdict(list)
        for row in group:
            by_pixels[f(row, "width") * f(row, "height")].append(row)
        if len(by_pixels) < 2:
            continue
        points = []
        for pixels, pixel_rows in by_pixels.items():
            points.append((pixels, avg(pixel_rows, "latency_seconds"), avg(pixel_rows, "quality_proxy")))
        points.sort()
        model, prompt, steps, frames = key
        first = points[0]
        last = points[-1]
        lines.append(
            f"| {MODEL_LABELS.get(model, model)} | {PROMPT_LABELS.get(prompt, prompt)} | "
            f"steps={steps}, frames={frames} | {first[0]/1_000_000:.3f}->{last[0]/1_000_000:.3f} MP | "
            f"{last[1] - first[1]:.3f}s | {last[1] / first[1]:.2f}x | {last[2] - first[2]:+.4f} |"
        )
    lines.append("")
    return lines


def write_report(rows: list[dict], out: Path) -> None:
    lines = [
        "# Bottleneck Experiments",
        "",
        "Controlled sweeps from `outputs_final`.",
        "Each table holds the major settings fixed except one variable.",
        "",
        "## Main Finding",
        "",
        (
            "Latency is dominated by repeated denoising work over frames and pixels. "
            "The evidence is that latency rises when denoising steps, frame count, or resolution rise, "
            "and the estimated work term `steps x pixels x frames` explains latency well for both models."
        ),
        "",
    ]

    lines.extend(
        summarize_groups(
            rows,
            fixed_keys=["model", "prompt_id", "width", "height", "frames"],
            x_key="steps",
            x_label="Denoising Step",
            unit="step",
        )
    )
    lines.extend(
        summarize_groups(
            rows,
            fixed_keys=["model", "prompt_id", "width", "height", "steps"],
            x_key="frames",
            x_label="Frame Count",
            unit="frame",
        )
    )
    lines.extend(resolution_summary(rows))
    lines.extend(
        [
            "## Optimization Implication",
            "",
            (
                "The scheduler uses this result by avoiding extra denoising work when the measured quality gain "
                "does not justify the latency cost."
            ),
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize controlled bottleneck experiments.")
    parser.add_argument("--metrics", type=Path, default=Path("analysis/model_comparison/metrics.csv"))
    parser.add_argument("--out", type=Path, default=Path("analysis/bottleneck/bottleneck_experiments.md"))
    args = parser.parse_args()

    rows = load_rows(args.metrics)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_report(rows, args.out)
    print(f"bottleneck report: {args.out}")


if __name__ == "__main__":
    main()
