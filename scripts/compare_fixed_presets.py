#!/usr/bin/env python3
"""Compare budget-aware selections against fixed video-generation presets."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


BUDGETS = [1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 70.0, 100.0]
FIXED_PRESETS = {
    "fixed_ltx_preview": "ltx_fast_384x640_49f_20s",
    "fixed_ltx_quality": "ltx_quality_512x704_81f_30s",
    "fixed_cogvideox_preview": "cogvideox_480x768_17f_15s",
    "fixed_cogvideox_quality": "cogvideox_480x768_49f_50s",
}
PROMPT_LABELS = {
    "static_landscape": "static landscape",
    "walking_person": "walking person",
    "fast_action": "fast action",
}
MODEL_LABELS = {"ltx": "LTX-Video", "cogvideox": "CogVideoX-2B"}


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_valid(row: dict) -> bool:
    return row.get("valid_video", "").lower() == "true"


def as_float(row: dict, key: str) -> float:
    return float(row[key])


def best_under_budget(rows: list[dict], budget: float) -> dict | None:
    feasible = [row for row in rows if is_valid(row) and as_float(row, "latency_seconds") <= budget]
    if not feasible:
        return None
    return max(feasible, key=lambda row: (as_float(row, "quality_proxy"), -as_float(row, "latency_seconds")))


def best_fixed_under_budget(rows: list[dict], budget: float) -> tuple[str, dict] | tuple[str, None]:
    candidates = []
    for preset_name, config_id in FIXED_PRESETS.items():
        for row in rows:
            if row["config_id"] == config_id and is_valid(row) and as_float(row, "latency_seconds") <= budget:
                candidates.append((preset_name, row))
    if not candidates:
        return "", None
    return max(candidates, key=lambda item: (as_float(item[1], "quality_proxy"), -as_float(item[1], "latency_seconds")))


def fixed_status(rows: list[dict], budget: float) -> str:
    statuses = []
    for preset_name, config_id in FIXED_PRESETS.items():
        matches = [row for row in rows if row["config_id"] == config_id]
        if not matches:
            continue
        row = matches[0]
        latency = as_float(row, "latency_seconds")
        if latency <= budget and is_valid(row):
            statuses.append(f"{preset_name}: fits ({latency:.2f}s, q={as_float(row, 'quality_proxy'):.4f})")
        elif latency > budget:
            statuses.append(f"{preset_name}: over budget ({latency:.2f}s)")
        else:
            statuses.append(f"{preset_name}: invalid")
    return "; ".join(statuses)


def comparison_rows(rows: list[dict]) -> list[dict]:
    output = []
    prompts = sorted({row["prompt_id"] for row in rows})
    for prompt_id in prompts:
        prompt_rows = [row for row in rows if row["prompt_id"] == prompt_id]
        for budget in BUDGETS:
            scheduler = best_under_budget(prompt_rows, budget)
            fixed_name, fixed = best_fixed_under_budget(prompt_rows, budget)
            if scheduler is None:
                continue
            scheduler_quality = as_float(scheduler, "quality_proxy")
            fixed_quality = as_float(fixed, "quality_proxy") if fixed else None
            output.append(
                {
                    "prompt_id": prompt_id,
                    "budget_seconds": budget,
                    "scheduler_run": scheduler["run_id"],
                    "scheduler_model": scheduler["model"],
                    "scheduler_config": scheduler["config_id"],
                    "scheduler_latency": f"{as_float(scheduler, 'latency_seconds'):.6f}",
                    "scheduler_quality": f"{scheduler_quality:.4f}",
                    "best_fixed_preset": fixed_name,
                    "best_fixed_run": fixed["run_id"] if fixed else "",
                    "best_fixed_latency": f"{as_float(fixed, 'latency_seconds'):.6f}" if fixed else "",
                    "best_fixed_quality": f"{fixed_quality:.4f}" if fixed else "",
                    "quality_gain": f"{(scheduler_quality - fixed_quality):.4f}" if fixed else "",
                    "fixed_preset_status": fixed_status(prompt_rows, budget),
                }
            )
    return output


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: Path) -> None:
    wins = [row for row in rows if row["quality_gain"] and float(row["quality_gain"]) > 0]
    ties = [row for row in rows if row["quality_gain"] and abs(float(row["quality_gain"])) <= 1e-9]
    no_fixed = [row for row in rows if not row["best_fixed_preset"]]
    comparable = [row for row in rows if row["best_fixed_preset"]]
    avg_gain = sum(float(row["quality_gain"]) for row in comparable) / len(comparable) if comparable else 0.0

    lines = [
        "# Fixed Preset Comparison",
        "",
        "Fixed presets used for the baseline comparison:",
        "",
    ]
    lines.extend(f"- `{name}`: `{config}`" for name, config in FIXED_PRESETS.items())
    lines.extend(
        [
            "",
            "A fixed preset only counts if it produces a valid video under the same latency budget.",
            "",
            "## Summary",
            "",
            f"- Scheduler comparisons: {len(rows)} prompt-budget cases",
            f"- Cases where no fixed preset fits the budget: {len(no_fixed)}",
            f"- Cases where scheduler beats the best fitting fixed preset: {len(wins)}",
            f"- Cases where scheduler ties the best fitting fixed preset: {len(ties)}",
            f"- Mean quality gain over fitting fixed presets: {avg_gain:.4f}",
            "",
            "## Representative Cases",
            "",
            "| Prompt | Budget | Scheduler choice | Scheduler quality | Best fixed preset | Fixed quality | Gain |",
            "| --- | ---: | --- | ---: | --- | ---: | ---: |",
        ]
    )

    interesting = [
        row
        for row in rows
        if row["budget_seconds"] in {1.0, 2.0, 5.0, 20.0, 40.0}
        and row["prompt_id"] in {"fast_action", "walking_person", "static_landscape"}
    ]
    for row in interesting:
        fixed_quality = row["best_fixed_quality"] or "n/a"
        gain = row["quality_gain"] or "n/a"
        fixed_name = row["best_fixed_preset"] or "none fits"
        lines.append(
            f"| {PROMPT_LABELS.get(row['prompt_id'], row['prompt_id'])} | "
            f"{float(row['budget_seconds']):.1f}s | "
            f"{MODEL_LABELS.get(row['scheduler_model'], row['scheduler_model'])} / `{row['scheduler_config']}` | "
            f"{float(row['scheduler_quality']):.4f} | "
            f"{fixed_name} | {fixed_quality} | {gain} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            (
                "A fixed preset is included only if it is valid and within the same latency budget. "
                "The scheduler row is the highest-quality valid run under that budget."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare V-Scale scheduler choices against fixed presets.")
    parser.add_argument("--metrics", type=Path, default=Path("analysis/model_comparison/metrics.csv"))
    parser.add_argument("--out", type=Path, default=Path("analysis/model_comparison"))
    args = parser.parse_args()

    rows = comparison_rows(load_rows(args.metrics))
    write_csv(rows, args.out / "fixed_preset_comparison.csv")
    write_markdown(rows, args.out / "fixed_preset_comparison.md")
    print(f"comparison: {args.out / 'fixed_preset_comparison.csv'}")
    print(f"summary: {args.out / 'fixed_preset_comparison.md'}")


if __name__ == "__main__":
    main()
