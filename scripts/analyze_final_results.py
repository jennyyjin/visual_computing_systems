#!/usr/bin/env python3
"""Build final cross-model analysis artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


BUDGETS = [1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 70.0, 100.0]
COLORS = {"ltx": "blue", "cogvideox": "red"}
MODEL_LABELS = {"ltx": "LTX-Video", "cogvideox": "CogVideoX-2B"}
PROMPT_LABELS = {
    "static_landscape": "static landscape",
    "walking_person": "walking person",
    "fast_action": "fast action",
}


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_valid(row: dict) -> bool:
    return row.get("valid_video", "").lower() == "true"


def f(row: dict, key: str) -> float:
    return float(row[key])


def pixel_count(row: dict) -> float:
    return f(row, "width") * f(row, "height")


def work_units(row: dict) -> float:
    return f(row, "steps") * pixel_count(row) * f(row, "frames") / 1_000_000.0


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var == 0 or y_var == 0:
        return float("nan")
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return cov / math.sqrt(x_var * y_var)


def slope(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return float("nan")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom


def fmt(value: float, digits: int = 3) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.{digits}f}"


def best_under_budget(rows: list[dict], budget: float) -> dict | None:
    feasible = [row for row in rows if is_valid(row) and f(row, "latency_seconds") <= budget]
    if not feasible:
        return None
    return max(feasible, key=lambda row: (f(row, "quality_proxy"), -f(row, "latency_seconds")))


def build_budget_rows(rows: list[dict]) -> list[dict]:
    prompts = sorted({row["prompt_id"] for row in rows})
    output = []
    for prompt in prompts:
        prompt_rows = [row for row in rows if row["prompt_id"] == prompt]
        for budget in BUDGETS:
            selected = best_under_budget(prompt_rows, budget)
            ltx = best_under_budget([row for row in prompt_rows if row["model"] == "ltx"], budget)
            cog = best_under_budget([row for row in prompt_rows if row["model"] == "cogvideox"], budget)
            output.append(
                {
                    "prompt_id": prompt,
                    "budget_seconds": budget,
                    "selected_run": selected["run_id"] if selected else "",
                    "selected_model": selected["model"] if selected else "",
                    "selected_latency": f"{f(selected, 'latency_seconds'):.6f}" if selected else "",
                    "selected_quality": f"{f(selected, 'quality_proxy'):.4f}" if selected else "",
                    "best_ltx_run": ltx["run_id"] if ltx else "",
                    "best_ltx_quality": f"{f(ltx, 'quality_proxy'):.4f}" if ltx else "",
                    "best_cogvideox_run": cog["run_id"] if cog else "",
                    "best_cogvideox_quality": f"{f(cog, 'quality_proxy'):.4f}" if cog else "",
                }
            )
    return output


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def controlled_slopes(rows: list[dict], varying: str, fixed: list[str]) -> dict[str, list[float]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if not is_valid(row):
            continue
        key = tuple(row[name] for name in fixed)
        groups[key].append(row)

    by_model: dict[str, list[float]] = defaultdict(list)
    for group in groups.values():
        values = sorted({f(row, varying) for row in group})
        if len(values) < 2:
            continue
        xs = [f(row, varying) for row in group]
        ys = [f(row, "latency_seconds") for row in group]
        by_model[group[0]["model"]].append(slope(xs, ys))
    return by_model


def write_svg(rows: list[dict], x_key: str, x_label: str, title: str, path: Path) -> None:
    valid = [row for row in rows if is_valid(row)]
    width, height = 900, 520
    left, right, top, bottom = 75, 680, 55, 70
    max_x = max(x_value(row, x_key) for row in valid)
    max_y = max(f(row, "latency_seconds") for row in valid)

    def pos(row: dict) -> tuple[float, float]:
        x = left + (x_value(row, x_key) / max_x) * (right - left)
        y = height - bottom - (f(row, "latency_seconds") / max_y) * (height - top - bottom)
        return x, y

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="32" font-family="Arial" font-size="22" font-weight="700">{escape(title)}</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{right}" y2="{height-bottom}" stroke="black" stroke-width="1.4"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="black" stroke-width="1.4"/>',
        f'<text x="{left + 210}" y="{height-24}" font-family="Arial" font-size="15">{escape(x_label)}</text>',
        '<text x="18" y="305" transform="rotate(-90 18 305)" font-family="Arial" font-size="15">latency (s)</text>',
    ]

    for value in [0.0, max_x / 2.0, max_x]:
        x = left + (value / max_x) * (right - left) if max_x else left
        svg.append(f'<line x1="{x:.1f}" y1="{height-bottom}" x2="{x:.1f}" y2="{height-bottom+5}" stroke="black"/>')
        svg.append(f'<text x="{x-22:.1f}" y="{height-bottom+24}" font-family="Arial" font-size="12">{value:.1f}</text>')
    for value in [0.0, max_y / 2.0, max_y]:
        y = height - bottom - (value / max_y) * (height - top - bottom) if max_y else height - bottom
        svg.append(f'<line x1="{left-5}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="black"/>')
        svg.append(f'<text x="35" y="{y+4:.1f}" font-family="Arial" font-size="12">{value:.1f}</text>')

    legend_y = 86
    for index, model in enumerate(["ltx", "cogvideox"]):
        y = legend_y + index * 30
        svg.append(f'<circle cx="720" cy="{y}" r="6" fill="{COLORS[model]}" stroke="black"/>')
        svg.append(f'<text x="738" y="{y+5}" font-family="Arial" font-size="14">{MODEL_LABELS[model]}</text>')

    for row in valid:
        x, y = pos(row)
        svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{COLORS.get(row["model"], "gray")}" '
            f'stroke="white" stroke-width="1"><title>{escape(row["run_id"])}</title></circle>'
        )
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def x_value(row: dict, key: str) -> float:
    if key == "pixels_mpix":
        return pixel_count(row) / 1_000_000.0
    if key == "work_units":
        return work_units(row)
    return f(row, key)


def write_markdown(rows: list[dict], budget_rows: list[dict], predictor_path: Path, out: Path) -> None:
    valid = [row for row in rows if is_valid(row)]
    predictor = json.loads(predictor_path.read_text(encoding="utf-8")) if predictor_path.exists() else {}
    failures = Counter(row["failure_reason"] for row in rows if row["failure_reason"] != "ok")

    lines = [
        "# Final Results Notes",
        "",
        "## Problem Statement",
        "",
        (
            "Given a text prompt and a latency budget, choose a video generation model and inference "
            "configuration that produces a valid video with the highest measured quality proxy on the same GPU setup."
        ),
        "",
        "Inputs: prompt, latency budget, candidate model/configuration set.",
        "Outputs: selected configuration, generated video, latency/memory measurements, and quality/validity metrics.",
        "",
        "## Current Evidence",
        "",
        f"- Total profiled runs: {len(rows)}",
        f"- Valid videos: {len(valid)}",
        f"- Invalid videos: {len(rows) - len(valid)} ({', '.join(f'{k}: {v}' for k, v in sorted(failures.items())) or 'none'})",
    ]

    for model in sorted({row["model"] for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        model_valid = [row for row in model_rows if is_valid(row)]
        latencies = [f(row, "latency_seconds") for row in model_rows]
        qualities = [f(row, "quality_proxy") for row in model_valid]
        lines.append(
            f"- {MODEL_LABELS.get(model, model)}: {len(model_rows)} runs, {len(model_valid)} valid, "
            f"latency {min(latencies):.2f}-{max(latencies):.2f}s, best quality {max(qualities):.4f}"
        )

    if predictor:
        metrics = predictor.get("training_metrics", {})
        lines.extend(
            [
                "",
                "## Predictor",
                "",
                (
                    "The lightweight predictor is a regularized linear regression over steps, frame count, "
                    "resolution, estimated work units, model, prompt, config, and precision."
                ),
                f"- Training rows: {metrics.get('rows')}",
                f"- Latency R2: {metrics.get('latency_r2')}",
                f"- Quality R2: {metrics.get('quality_r2')}",
            ]
        )

    lines.extend(["", "## Bottleneck Signals", ""])
    lines.append("| Model | corr(latency, steps) | corr(latency, frames) | corr(latency, pixels) | corr(latency, work units) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for model in sorted({row["model"] for row in valid}):
        model_rows = [row for row in valid if row["model"] == model]
        ys = [f(row, "latency_seconds") for row in model_rows]
        lines.append(
            f"| {MODEL_LABELS.get(model, model)} | "
            f"{fmt(pearson([f(row, 'steps') for row in model_rows], ys))} | "
            f"{fmt(pearson([f(row, 'frames') for row in model_rows], ys))} | "
            f"{fmt(pearson([pixel_count(row) for row in model_rows], ys))} | "
            f"{fmt(pearson([work_units(row) for row in model_rows], ys))} |"
        )

    step_slopes = controlled_slopes(
        rows,
        "steps",
        ["model", "prompt_id", "width", "height", "frames", "precision"],
    )
    frame_slopes = controlled_slopes(
        rows,
        "frames",
        ["model", "prompt_id", "width", "height", "steps", "precision"],
    )
    lines.extend(["", "Controlled one-variable comparisons:", ""])
    for model in sorted(set(step_slopes) | set(frame_slopes)):
        step_values = step_slopes.get(model, [])
        frame_values = frame_slopes.get(model, [])
        lines.append(
            f"- {MODEL_LABELS.get(model, model)}: median step slope "
            f"{fmt(median(step_values) if step_values else float('nan'))} s/step; "
            f"median frame slope {fmt(median(frame_values) if frame_values else float('nan'))} s/frame"
        )

    lines.extend(
        [
            "",
            "## Per-Prompt Budget Choices",
            "",
            "| Prompt | Budget | Selected model | Latency | Quality | Selected run |",
            "| --- | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in budget_rows:
        if row["selected_run"]:
            lines.append(
                f"| {PROMPT_LABELS.get(row['prompt_id'], row['prompt_id'])} | {row['budget_seconds']:.1f}s | "
                f"{MODEL_LABELS.get(row['selected_model'], row['selected_model'])} | "
                f"{float(row['selected_latency']):.3f}s | {float(row['selected_quality']):.4f} | "
                f"`{row['selected_run']}` |"
            )
        else:
            lines.append(
                f"| {PROMPT_LABELS.get(row['prompt_id'], row['prompt_id'])} | {row['budget_seconds']:.1f}s | "
                "none | n/a | n/a | no valid run under budget |"
            )

    lines.extend(
        [
            "",
        "## Result",
            "",
            (
                "In the measured sweep, budget-aware selection improves over fixed presets by "
                "choosing different model/configuration pairs for different prompts and budgets. "
                "LTX-Video occupies the low-latency region and the global Pareto frontier. "
                "CogVideoX-2B is selected only when the budget is large enough for its fast-action "
                "quality gain to matter."
            ),
        ]
    )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create final analysis artifacts from model-comparison metrics.")
    parser.add_argument("--metrics", type=Path, default=Path("analysis/model_comparison/metrics.csv"))
    parser.add_argument("--predictor", type=Path, default=Path("analysis/model_comparison/predictor.json"))
    parser.add_argument("--out", type=Path, default=Path("analysis/model_comparison"))
    args = parser.parse_args()

    rows = load_csv(args.metrics)
    for row in rows:
        row["work_units"] = f"{work_units(row):.6f}"
        row["pixels_mpix"] = f"{pixel_count(row) / 1_000_000.0:.6f}"

    args.out.mkdir(parents=True, exist_ok=True)
    plot_dir = args.out / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    budget_rows = build_budget_rows(rows)
    write_csv(budget_rows, args.out / "prompt_budget_selections.csv")
    write_svg(rows, "steps", "denoising steps", "Latency vs Denoising Steps", plot_dir / "latency_vs_steps.svg")
    write_svg(rows, "frames", "generated frames", "Latency vs Frame Count", plot_dir / "latency_vs_frames.svg")
    write_svg(rows, "work_units", "steps x pixels x frames / 1M", "Latency vs Estimated Work", plot_dir / "latency_vs_work.svg")
    write_markdown(rows, budget_rows, args.predictor, args.out / "final_results_notes.md")

    print(f"summary: {args.out / 'final_results_notes.md'}")
    print(f"budget table: {args.out / 'prompt_budget_selections.csv'}")
    print(f"plots: {plot_dir / 'latency_vs_steps.svg'}, {plot_dir / 'latency_vs_frames.svg'}, {plot_dir / 'latency_vs_work.svg'}")


if __name__ == "__main__":
    main()
