#!/usr/bin/env python3
"""
Train lightweight latency and quality predictors from V-Scale metrics.
The predictor is a simple linear model with numeric and one-hot features.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


NUMERIC_FEATURES = [
    "steps",
    "width",
    "height",
    "frames",
    "pixel_count",
    "work_units",
]

CATEGORICAL_FEATURES = [
    "model",
    "prompt_id",
    "config_id",
    "precision",
]


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def numeric_value(row: dict, name: str) -> float:
    if name == "pixel_count":
        return float(row["width"]) * float(row["height"])
    if name == "work_units":
        return float(row["steps"]) * float(row["width"]) * float(row["height"]) * float(row["frames"]) / 1_000_000.0
    return float(row[name])


def build_vocab(rows: list[dict]) -> dict[str, list[str]]:
    return {
        name: sorted({row.get(name, "") for row in rows})
        for name in CATEGORICAL_FEATURES
    }


def raw_features(row: dict, vocab: dict[str, list[str]]) -> list[float]:
    features = [numeric_value(row, name) for name in NUMERIC_FEATURES]
    for name in CATEGORICAL_FEATURES:
        value = row.get(name, "")
        features.extend(1.0 if value == item else 0.0 for item in vocab[name])
    return features


def feature_names(vocab: dict[str, list[str]]) -> list[str]:
    names = list(NUMERIC_FEATURES)
    for name in CATEGORICAL_FEATURES:
        names.extend(f"{name}={item}" for item in vocab[name])
    return names


def normalize_matrix(matrix: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    cols = len(matrix[0])
    means = []
    stds = []
    for col in range(cols):
        values = [row[col] for row in matrix]
        mean = sum(values) / len(values)
        var = sum((value - mean) ** 2 for value in values) / len(values)
        std = var ** 0.5 or 1.0
        means.append(mean)
        stds.append(std)
    normalized = [
        [1.0] + [(value - means[idx]) / stds[idx] for idx, value in enumerate(row)]
        for row in matrix
    ]
    return normalized, means, stds


def fit_linear_model(x: list[list[float]], y: list[float], epochs: int, lr: float, l2: float) -> list[float]:
    weights = [0.0 for _ in range(len(x[0]))]
    n = len(x)
    for _ in range(epochs):
        grads = [0.0 for _ in weights]
        for features, target in zip(x, y):
            pred = sum(weight * value for weight, value in zip(weights, features))
            err = pred - target
            for idx, value in enumerate(features):
                grads[idx] += err * value
        for idx in range(len(weights)):
            penalty = 0.0 if idx == 0 else l2 * weights[idx]
            weights[idx] -= lr * ((grads[idx] / n) + penalty)
    return weights


def predict(weights: list[float], features: list[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, features))


def r2_score(y: list[float], y_hat: list[float]) -> float:
    mean_y = sum(y) / len(y)
    total = sum((value - mean_y) ** 2 for value in y)
    residual = sum((value - pred) ** 2 for value, pred in zip(y, y_hat))
    return 0.0 if total == 0 else 1.0 - residual / total


def main() -> None:
    parser = argparse.ArgumentParser(description="Train lightweight latency and quality predictors from V-Scale metrics.")
    parser.add_argument("--metrics", type=Path, default=Path("analysis/eval/metrics.csv"))
    parser.add_argument("--out", type=Path, default=Path("analysis/predictor.json"))
    parser.add_argument("--epochs", type=int, default=5000)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--l2", type=float, default=0.0001)
    args = parser.parse_args()

    rows = load_rows(args.metrics)
    vocab = build_vocab(rows)
    raw_x = [raw_features(row, vocab) for row in rows]
    x, means, stds = normalize_matrix(raw_x)
    latency_y = [float(row["latency_seconds"]) for row in rows]
    quality_y = [float(row["quality_proxy"]) for row in rows]

    latency_weights = fit_linear_model(x, latency_y, args.epochs, args.lr, args.l2)
    quality_weights = fit_linear_model(x, quality_y, args.epochs, args.lr, args.l2)
    latency_hat = [predict(latency_weights, row) for row in x]
    quality_hat = [predict(quality_weights, row) for row in x]

    model = {
        "feature_names": feature_names(vocab),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "vocab": vocab,
        "means": means,
        "stds": stds,
        "latency_weights": latency_weights,
        "quality_weights": quality_weights,
        "training_metrics": {
            "rows": len(rows),
            "latency_r2": round(r2_score(latency_y, latency_hat), 4),
            "quality_r2": round(r2_score(quality_y, quality_hat), 4),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)

    print(f"trained predictor: {args.out}")
    print(json.dumps(model["training_metrics"], indent=2))


if __name__ == "__main__":
    main()
