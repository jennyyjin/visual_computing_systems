#!/usr/bin/env python3
"""
Compute Pareto-optimal runs and simple budget-based selections.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def as_float(row: dict, key: str) -> float:
    return float(row[key])


def is_dominated(row: dict, candidates: list[dict]) -> bool:
    latency = as_float(row, "latency_seconds")
    quality = as_float(row, "quality_proxy")
    for other in candidates:
        if other is row:
            continue
        other_latency = as_float(other, "latency_seconds")
        other_quality = as_float(other, "quality_proxy")
        at_least_as_good = other_latency <= latency and other_quality >= quality
        strictly_better = other_latency < latency or other_quality > quality
        if at_least_as_good and strictly_better:
            return True
    return False


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def select_for_budgets(rows: list[dict], budgets: list[float]) -> list[dict]:
    selected = []
    valid_rows = [row for row in rows if row["valid_video"] == "true"]
    for budget in budgets:
        feasible = [row for row in valid_rows if as_float(row, "latency_seconds") <= budget * 1.10]
        if not feasible:
            continue
        best = max(feasible, key=lambda row: (as_float(row, "quality_proxy"), -as_float(row, "latency_seconds")))
        selected.append({"budget_seconds": budget, **best})
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, default=Path("outputs/eval/metrics.csv"))
    parser.add_argument("--out", type=Path, default=Path("outputs/eval"))
    parser.add_argument("--budgets", nargs="*", type=float, default=[0.15, 0.5, 1.0])
    args = parser.parse_args()

    rows = load_rows(args.metrics)
    valid_rows = [row for row in rows if row["valid_video"] == "true"]
    frontier = [row for row in valid_rows if not is_dominated(row, valid_rows)]
    frontier.sort(key=lambda row: as_float(row, "latency_seconds"))
    selected = select_for_budgets(rows, args.budgets)

    if frontier:
        write_rows(args.out / "pareto_frontier.csv", frontier)
    if selected:
        write_rows(args.out / "budget_selections.csv", selected)

    print(f"pareto frontier points: {len(frontier)}")
    print(f"budget selections: {len(selected)}")


if __name__ == "__main__":
    main()
