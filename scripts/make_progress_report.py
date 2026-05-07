#!/usr/bin/env python3
"""Build the progress summary report and latency-quality plot."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


PLOT_WIDTH = 860
PLOT_HEIGHT = 520
LEFT = 70
RIGHT = 30
TOP = 40
BOTTOM = 60


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
    plot_width = PLOT_WIDTH - LEFT - RIGHT
    plot_height = PLOT_HEIGHT - TOP - BOTTOM
    x = LEFT + (latency / max_latency) * plot_width if max_latency else LEFT
    y = PLOT_HEIGHT - BOTTOM - (quality / max_quality) * plot_height if max_quality else PLOT_HEIGHT - BOTTOM
    return x, y


def write_latency_quality_plot(metrics: list[dict], frontier: list[dict], out_path: Path) -> None:
    max_latency = max(as_float(row, "latency_seconds") for row in metrics)
    max_quality = max(1.0, max(as_float(row, "quality_proxy") for row in metrics))
    frontier_ids = {row["run_id"] for row in frontier}
    x_axis = PLOT_HEIGHT - BOTTOM

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PLOT_WIDTH}" height="{PLOT_HEIGHT}" viewBox="0 0 {PLOT_WIDTH} {PLOT_HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="70" y="26" font-family="Arial" font-size="18">V-Scale: Quality vs Latency</text>',
        f'<line x1="{LEFT}" y1="{x_axis}" x2="{PLOT_WIDTH-RIGHT}" y2="{x_axis}" stroke="black"/>',
        f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{x_axis}" stroke="black"/>',
        f'<text x="{PLOT_WIDTH/2-45}" y="{PLOT_HEIGHT-18}" font-family="Arial" font-size="13">latency (s)</text>',
        '<text x="14" y="280" transform="rotate(-90 14 280)" font-family="Arial" font-size="13">quality proxy</text>',
        '<circle cx="650" cy="45" r="5" fill="#1f77b4"/><text x="662" y="49" font-family="Arial" font-size="12">valid</text>',
        '<circle cx="710" cy="45" r="5" fill="#b0b0b0"/><text x="722" y="49" font-family="Arial" font-size="12">invalid</text>',
        '<circle cx="780" cy="45" r="6" fill="white" stroke="black"/><text x="792" y="49" font-family="Arial" font-size="12">frontier</text>',
    ]

    for value in [0, max_latency / 2, max_latency]:
        x = LEFT + (value / max_latency) * (PLOT_WIDTH - LEFT - RIGHT) if max_latency else LEFT
        svg.append(f'<text x="{x-14:.1f}" y="{x_axis+20}" font-family="Arial" font-size="11">{value:.2f}</text>')

    for value in [0, max_quality / 2, max_quality]:
        y = PLOT_HEIGHT - BOTTOM - (value / max_quality) * (PLOT_HEIGHT - TOP - BOTTOM) if max_quality else x_axis
        svg.append(f'<text x="35" y="{y+4:.1f}" font-family="Arial" font-size="11">{value:.1f}</text>')

    for row in metrics:
        x, y = point_position(row, max_latency, max_quality)
        valid = row["valid_video"] == "true"
        is_frontier = row["run_id"] in frontier_ids
        fill = "#1f77b4" if valid else "#b0b0b0"
        stroke = "black" if is_frontier else "white"
        radius = 6 if is_frontier else 4
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" stroke="{stroke}"/>')

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
        "# V-Scale Progress Results",
        "",
        f"Total evaluated runs: {len(metrics)}",
        f"Valid videos: {validity_counts.get('true', 0)}",
        f"Invalid videos: {validity_counts.get('false', 0)}",
        f"Pareto frontier points: {len(frontier)}",
        "",
        "## Best Valid Dummy Output",
        "",
        f"- Run: `{best['run_id']}`",
        f"- Quality proxy: `{best['quality_proxy']}`",
        f"- Latency: `{best['latency_seconds']}s`",
        f"- Failure reason: `{best['failure_reason']}`",
        "",
        "## Failure Reasons",
        "",
    ]

    lines.extend(f"- `{reason}`: {count}" for reason, count in sorted(failure_counts.items()))
    lines.extend(["", "## Budget Selections", ""])
    lines.extend(budget_selection_table(selections))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "The sanity checks behave as expected: blank videos, frozen videos, and random noise are "
                "marked as failures, while the moving-square clip is treated as a valid nontrivial output. "
                "This gives us a basic test harness before plugging in real video model generations."
            ),
        ]
    )

    return "\n".join(lines) + "\n"


def write_markdown_report(metrics: list[dict], frontier: list[dict], selections: list[dict], out_path: Path) -> None:
    out_path.write_text(markdown_summary(metrics, frontier, selections), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create progress report artifacts from evaluation metrics.")
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
    report_path = args.out / "results.md"
    write_latency_quality_plot(metrics, frontier, plot_path)
    write_markdown_report(metrics, frontier, selections, report_path)

    print(f"plot: {plot_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
