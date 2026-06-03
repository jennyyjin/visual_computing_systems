# Progress Documentation 

## Project Question
Can V-Scale choose better video generation settings than fixed presets under the same latency or memory budget?

## Current Focus
The final pipeline profiles real LTX-Video and CogVideoX runs, evaluates the generated videos, and compares fixed presets against budget-aware scheduling.

## What Is Implemented
- A fixed prompt suite with spatial-detail, medium-motion, and fast-action prompts
- A small configuration sweep over steps, resolution, and frame count
- A shared run format with `metadata.json` and frame directories
- Evaluation metrics for nonblankness, motion, sharpness, stability, and a simple quality proxy
- Pareto frontier and budget-selection scripts
- A lightweight predictor and scheduler trace script
- Reporting scripts for final metrics, plots, and tables

## Model Selection
We use the same evaluation harness for both model backends.

- **CogVideoX-2B:** real-model backend. It is relatively lightweight to run, integrates cleanly with Diffusers, and exposes the main inference parameters we want to study, including denoising steps, frame count, resolution, and guidance scale 
- **LTX-Video:** another backend for cross-model evaluation. It is designed around fast inference and low-step generation, making it a useful contrast to CogVideoX-2B for studying latency-quality tradeoffs 

## Prompt Selection
The prompt file is `configs/prompts.json`. The prompts are fixed so that every configuration is evaluated on the same cases.
- `static_landscape`: low motion, spatial-detail focused
- `walking_person`: medium motion, temporal-consistency focused
- `fast_action`: high motion, motion focused
These prompts cover the main tradeoffs the scheduler should eventually reason about: detail, consistency, and motion.

## Metrics
The evaluator writes `analysis/eval/metrics.csv`. Current quality metrics:
- `spatial_std`: detects blank or low-contrast videos
- `temporal_delta`: measures frame-to-frame motion
- `sharpness_score`: measures local image variation
- `stability_score`: penalizes excessive random flicker
- `quality_proxy`: combines the above into one simple score for plotting
- `valid_video` and `failure_reason`: mark obvious failures
Current performance metrics: 
- `latency_seconds`
- `peak_memory_mb`
- steps, width, height, frame count, and precision for each run

## Current Experiment
The final run set contains 54 profiled videos across three prompts and two model families. The analysis computes validity, quality proxies, latency, peak memory, Pareto frontiers, fixed-preset comparisons, and bottleneck summaries.

## Run Commands 
```bash
python3 scripts/evaluate_outputs.py \
  --manifest outputs_final/ltx_video/manifest.csv \
  --out analysis/ltx_video/eval

python3 scripts/evaluate_outputs.py \
  --manifest outputs_final/cogvideox/manifest.csv \
  --out analysis/cogvideox/eval

python3 scripts/pareto_select.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison

python3 scripts/train_predictor.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison/predictor.json

python3 scripts/compare_fixed_presets.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison
```

## Generated Artifacts
- `outputs_final/ltx_video/manifest.csv`
- `outputs_final/cogvideox/manifest.csv`
- `analysis/model_comparison/metrics.csv`
- `analysis/model_comparison/pareto_frontier.csv`
- `analysis/model_comparison/fixed_preset_comparison.csv`
- `analysis/model_comparison/predictor.json`
- `analysis/bottleneck/bottleneck_experiments.md`
- `analysis/offload_test/offload_comparison.md`

## Remaining Work
1. Add stronger perceptual or prompt-alignment metrics if time allows
2. Repeat selected runs to estimate latency variance
3. Expand the model/configuration sweep if more GPU time is available
