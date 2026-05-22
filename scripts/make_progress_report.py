#!/usr/bin/env python3
"""Build a concise evaluation summary and latency-quality plot."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from html import escape
from pathlib import Path


PLOT_WIDTH = 1040
PLOT_HEIGHT = 560
LEFT = 78
CHART_RIGHT = 760
TOP = 58
BOTTOM = 72
LEGEND_X = 800
BASELINE_COLORS = {
    "white": "gray",
    "black": "black",
    "static_frame": "purple",
    "noise": "orange",
    "moving_square": "green",
    "ltx": "blue",
    "cogvideox": "red",
}
MODEL_LABELS = {
    "white": "white baseline",
    "black": "black baseline",
    "static_frame": "static frame",
    "noise": "noise",
    "moving_square": "moving square",
    "ltx": "LTX-Video",
    "cogvideox": "CogVideoX-2B",
}


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_optional_csv(path: Path) -> list[dict]:
    return load_csv(path) if path.exists() else []


def as_float(row: dict, key: str) -> float:
    return float(row[key])


def point_position(row: dict, max_latency: float, max_quality: float) -> tuple[float, float]:
    latency = as_float(row, "latency_seconds")
    quality = as_float(row, "quality_proxy")
    plot_width = CHART_RIGHT - LEFT
    plot_height = PLOT_HEIGHT - TOP - BOTTOM
    x = LEFT + (latency / max_latency) * plot_width if max_latency else LEFT
    y = PLOT_HEIGHT - BOTTOM - (quality / max_quality) * plot_height if max_quality else PLOT_HEIGHT - BOTTOM
    return x, y


def baseline_color(name: str) -> str:
    return BASELINE_COLORS.get(name, "blue")


def model_label(name: str) -> str:
    return MODEL_LABELS.get(name, name.replace("_", " "))


def axis_ticks(max_value: float) -> list[float]:
    if max_value <= 0:
        return [0.0]
    return [0.0, max_value / 2.0, max_value]


def legend_rows(metrics: list[dict], frontier: list[dict]) -> list[tuple[str, str, str]]:
    present_models = []
    for row in metrics:
        model = row["model"]
        if model not in present_models:
            present_models.append(model)
    rows = [("model", model, model_label(model)) for model in present_models]
    if frontier:
        rows.append(("frontier", "frontier", "Pareto frontier"))
    if any(row.get("valid_video") == "false" for row in metrics):
        rows.append(("invalid", "invalid", "invalid run"))
    return rows


def write_latency_quality_plot(metrics: list[dict], frontier: list[dict], out_path: Path) -> None:
    max_latency = max(as_float(row, "latency_seconds") for row in metrics)
    max_quality = max(1.0, max(as_float(row, "quality_proxy") for row in metrics))
    frontier_ids = {row["run_id"] for row in frontier}
    x_axis = PLOT_HEIGHT - BOTTOM
    plot_width = CHART_RIGHT - LEFT
    plot_height = PLOT_HEIGHT - TOP - BOTTOM

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PLOT_WIDTH}" height="{PLOT_HEIGHT}" viewBox="0 0 {PLOT_WIDTH} {PLOT_HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="78" y="32" font-family="Arial" font-size="22" font-weight="700">Quality vs Latency</text>',
        f'<line x1="{LEFT}" y1="{x_axis}" x2="{CHART_RIGHT}" y2="{x_axis}" stroke="black" stroke-width="1.4"/>',
        f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{x_axis}" stroke="black" stroke-width="1.4"/>',
        f'<text x="{LEFT + plot_width / 2 - 35:.1f}" y="{PLOT_HEIGHT-22}" font-family="Arial" font-size="15">latency (s)</text>',
        '<text x="18" y="310" transform="rotate(-90 18 310)" font-family="Arial" font-size="15">quality proxy</text>',
        f'<text x="{LEGEND_X}" y="72" font-family="Arial" font-size="14" font-weight="700">Legend</text>',
    ]

    for value in axis_ticks(max_latency):
        x = LEFT + (value / max_latency) * plot_width if max_latency else LEFT
        if value > 0:
            svg.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{x_axis}" stroke="lightgray" stroke-width="0.8"/>')
        svg.append(f'<line x1="{x:.1f}" y1="{x_axis}" x2="{x:.1f}" y2="{x_axis+5}" stroke="black"/>')
        svg.append(f'<text x="{x-18:.1f}" y="{x_axis+24}" font-family="Arial" font-size="12">{value:.2f}</text>')

    for value in [0.0, 0.5, 1.0]:
        y = PLOT_HEIGHT - BOTTOM - (value / max_quality) * plot_height if max_quality else x_axis
        if value > 0:
            svg.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{CHART_RIGHT}" y2="{y:.1f}" stroke="lightgray" stroke-width="0.8"/>')
        svg.append(f'<line x1="{LEFT-5}" y1="{y:.1f}" x2="{LEFT}" y2="{y:.1f}" stroke="black"/>')
        svg.append(f'<text x="42" y="{y+4:.1f}" font-family="Arial" font-size="12">{value:.1f}</text>')

    for index, (kind, name, label) in enumerate(legend_rows(metrics, frontier)):
        y = 98 + index * 28
        if kind == "frontier":
            svg.append(f'<circle cx="{LEGEND_X+8}" cy="{y}" r="7" fill="white" stroke="black" stroke-width="2.5"/>')
        elif kind == "invalid":
            svg.append(f'<circle cx="{LEGEND_X+8}" cy="{y}" r="6" fill="white" stroke="black" stroke-width="1.5"/>')
            svg.append(f'<line x1="{LEGEND_X+3}" y1="{y-5}" x2="{LEGEND_X+13}" y2="{y+5}" stroke="black" stroke-width="1.5"/>')
            svg.append(f'<line x1="{LEGEND_X+13}" y1="{y-5}" x2="{LEGEND_X+3}" y2="{y+5}" stroke="black" stroke-width="1.5"/>')
        else:
            color = baseline_color(name)
            svg.append(f'<circle cx="{LEGEND_X+8}" cy="{y}" r="6" fill="{color}" stroke="black" stroke-width="1.2"/>')
        svg.append(f'<text x="{LEGEND_X+24}" y="{y+5}" font-family="Arial" font-size="13">{escape(label)}</text>')

    for row in metrics:
        x, y = point_position(row, max_latency, max_quality)
        is_frontier = row["run_id"] in frontier_ids
        is_valid = row.get("valid_video") != "false"
        fill = baseline_color(row["model"])
        stroke = "black" if is_frontier else "white"
        radius = 7 if is_frontier else 5.5
        width = 2.4 if is_frontier else 1.2
        opacity = "1.0" if is_valid else "0.35"
        svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}">'
            f'<title>{escape(row["run_id"])}: quality {row["quality_proxy"]}, latency {row["latency_seconds"]}s</title>'
            "</circle>"
        )
        if not is_valid:
            svg.append(f'<line x1="{x-4:.1f}" y1="{y-4:.1f}" x2="{x+4:.1f}" y2="{y+4:.1f}" stroke="black" stroke-width="1.4"/>')
            svg.append(f'<line x1="{x+4:.1f}" y1="{y-4:.1f}" x2="{x-4:.1f}" y2="{y+4:.1f}" stroke="black" stroke-width="1.4"/>')

    svg.append("</svg>")
    out_path.write_text("\n".join(svg), encoding="utf-8")


def best_valid_run(metrics: list[dict]) -> dict:
    valid = [row for row in metrics if row["valid_video"] == "true"]
    candidates = valid or metrics
    return max(candidates, key=lambda row: as_float(row, "quality_proxy"))


def budget_selection_table(selections: list[dict]) -> list[str]:
    if not selections:
        return ["No valid runs fit the requested budgets."]

    lines = [
        "| Budget | Selected run | Quality | Latency |",
        "| --- | --- | --- | --- |",
    ]
    for row in selections:
        lines.append(
            f"| {row['budget_seconds']}s | `{row['run_id']}` | {row['quality_proxy']} | {row['latency_seconds']}s |"
        )
    return lines


def markdown_summary(metrics: list[dict], frontier: list[dict], selections: list[dict]) -> str:
    validity_counts = Counter(row["valid_video"] for row in metrics)
    failure_counts = Counter(row["failure_reason"] for row in metrics)
    best = best_valid_run(metrics)

    lines = [
        "# Evaluation Summary",
        "",
        f"Total evaluated runs: {len(metrics)}",
        f"Valid videos: {validity_counts.get('true', 0)}",
        f"Invalid videos: {validity_counts.get('false', 0)}",
        f"Pareto frontier points: {len(frontier)}",
        "",
        "## Highest-Scoring Valid Run",
        "",
        f"- Run: `{best['run_id']}`",
        f"- Quality proxy: `{best['quality_proxy']}`",
        f"- Latency: `{best['latency_seconds']}s`",
        f"- Failure reason: `{best['failure_reason']}`",
        "",
        "## Validity Outcomes",
        "",
    ]

    lines.extend(f"- `{reason}`: {count}" for reason, count in sorted(failure_counts.items()))
    lines.extend(["", "## Budget-Constrained Selections", ""])
    lines.extend(budget_selection_table(selections))
    return "\n".join(lines) + "\n"


def write_markdown_report(metrics: list[dict], frontier: list[dict], selections: list[dict], out_path: Path) -> None:
    out_path.write_text(markdown_summary(metrics, frontier, selections), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create evaluation report artifacts from metrics.")
    parser.add_argument("--eval", type=Path, default=Path("outputs/eval"))
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = load_csv(args.eval / "metrics.csv")
    frontier = load_optional_csv(args.eval / "pareto_frontier.csv")
    selections = load_optional_csv(args.eval / "budget_selections.csv")

    args.out.mkdir(parents=True, exist_ok=True)
    plot_path = args.out / "latency_quality.svg"
    report_path = args.out / "evaluation_summary.md"
    write_latency_quality_plot(metrics, frontier, plot_path)
    write_markdown_report(metrics, frontier, selections, report_path)

    print(f"plot: {plot_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
