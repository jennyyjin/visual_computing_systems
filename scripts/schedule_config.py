#!/usr/bin/env python3
"""
Select the best predicted valid configuration under a latency budget.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def numeric_value(row: dict, name: str) -> float:
    if name == "pixel_count":
        return float(row["width"]) * float(row["height"])
    if name == "work_units":
        return float(row["steps"]) * float(row["width"]) * float(row["height"]) * float(row["frames"]) / 1_000_000.0
    return float(row[name])


def features(row: dict, model: dict) -> list[float]:
    raw = [numeric_value(row, name) for name in model["numeric_features"]]
    for name in model["categorical_features"]:
        value = row.get(name, "")
        raw.extend(1.0 if value == item else 0.0 for item in model["vocab"][name])
    normalized = [
        (value - model["means"][idx]) / model["stds"][idx]
        for idx, value in enumerate(raw)
    ]
    return [1.0] + normalized


def predict(weights: list[float], x: list[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, x))


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a V-Scale configuration under a latency budget.")
    parser.add_argument("--predictor", type=Path, default=Path("outputs/predictor.json"))
    parser.add_argument("--candidates", type=Path, default=Path("outputs/eval/metrics.csv"))
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--prompt-id", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--tolerance", type=float, default=0.10)
    parser.add_argument("--out", type=Path, default=Path("outputs/scheduler_trace.json"))
    args = parser.parse_args()

    with args.predictor.open("r", encoding="utf-8") as f:
        predictor = json.load(f)
    rows = load_csv(args.candidates)
    if args.prompt_id:
        rows = [row for row in rows if row["prompt_id"] == args.prompt_id]
    if args.model:
        rows = [row for row in rows if row["model"] == args.model]
    rows = [row for row in rows if row.get("valid_video", "true") == "true"]
    if not rows:
        raise SystemExit("no candidate rows match the requested filters")

    scored = []
    for row in rows:
        x = features(row, predictor)
        pred_latency = max(0.0, predict(predictor["latency_weights"], x))
        pred_quality = max(0.0, min(1.0, predict(predictor["quality_weights"], x)))
        scored.append(
            {
                **row,
                "predicted_latency_seconds": round(pred_latency, 6),
                "predicted_quality": round(pred_quality, 6),
                "within_budget": pred_latency <= args.budget * (1.0 + args.tolerance),
            }
        )

    feasible = [row for row in scored if row["within_budget"]]
    if not feasible:
        best = min(scored, key=lambda row: row["predicted_latency_seconds"])
        status = "no_feasible_candidate"
    else:
        best = max(feasible, key=lambda row: (row["predicted_quality"], -row["predicted_latency_seconds"]))
        status = "selected"

    trace = {
        "status": status,
        "budget_seconds": args.budget,
        "tolerance": args.tolerance,
        "prompt_id": args.prompt_id,
        "model": args.model,
        "selected": best,
        "num_candidates": len(scored),
        "num_feasible": len(feasible),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2)

    print(f"status: {status}")
    print(f"selected: {best['run_id']}")
    print(f"predicted latency: {best['predicted_latency_seconds']}s")
    print(f"predicted quality: {best['predicted_quality']}")
    print(f"trace: {args.out}")


if __name__ == "__main__":
    main()
