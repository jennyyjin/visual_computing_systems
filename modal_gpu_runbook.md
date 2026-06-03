# Modal GPU Runbook

Use this to produce real GPU outputs while keeping the same evaluation schema across model backends.

Modal is the GPU compute platform. It is not a video model. The output folders are named by experiment:

- `outputs_final/ltx_video`: LTX-Video runs generated on Modal
- `outputs_final/cogvideox`: CogVideoX-2B runs generated on Modal
- `analysis/model_comparison`: merged LTX-Video and CogVideoX metrics for comparison

## Recommended Model Order

1. **LTX-Video first:** fastest path to good-looking real outputs. Run the LTX configs across all three prompts and use these for the main qualitative figure.
2. **CogVideoX-2B second:** use as a stronger/contrasting baseline if Modal time allows. It is slower, but useful because it exposes the same denoising-step, resolution, frame-count, and guidance controls.
3. **Controlled outputs:** keep these only as evaluator diagnostics, not as model-quality results.

## One-Time Setup

```bash
python3 -m pip install modal
modal setup
```

## First Smoke Test

Run one short LTX generation before launching the whole sweep:

```bash
modal run scripts/run_modal_video_sweep.py \
  --backend ltx \
  --prompt-id static_landscape \
  --config-id ltx_fast_384x640_49f_20s \
  --out outputs_final/ltx_video \
  --batch-size 1
```

Then evaluate it:

```bash
python3 scripts/evaluate_outputs.py --runs outputs_final/ltx_video/runs --out analysis/ltx_video/eval
python3 scripts/pareto_select.py --metrics analysis/ltx_video/eval/metrics.csv --out analysis/ltx_video/eval
python3 scripts/make_progress_report.py --eval analysis/ltx_video/eval --out analysis/ltx_video
python3 scripts/make_frame_grid.py --runs outputs_final/ltx_video/runs --out analysis/ltx_video/frame_grid.svg
```

## Main LTX Sweep

This runs the two LTX configs over all three fixed prompts:

```bash
modal run scripts/run_modal_video_sweep.py \
  --backend ltx \
  --out outputs_final/ltx_video \
  --batch-size 1

python3 scripts/evaluate_outputs.py --runs outputs_final/ltx_video/runs --out analysis/ltx_video/eval
python3 scripts/pareto_select.py --metrics analysis/ltx_video/eval/metrics.csv --out analysis/ltx_video/eval
python3 scripts/train_predictor.py --metrics analysis/ltx_video/eval/metrics.csv --out analysis/ltx_video/predictor.json
python3 scripts/schedule_config.py \
  --predictor analysis/ltx_video/predictor.json \
  --candidates analysis/ltx_video/eval/metrics.csv \
  --budget 30 \
  --prompt-id fast_action \
  --out analysis/ltx_video/scheduler_trace.json
python3 scripts/make_progress_report.py --eval analysis/ltx_video/eval --out analysis/ltx_video
python3 scripts/make_frame_grid.py --runs outputs_final/ltx_video/runs --out analysis/ltx_video/frame_grid.svg
```

## CogVideoX Sweep

Run this after the LTX sweep:

```bash
modal run scripts/run_modal_video_sweep.py \
  --backend cogvideox \
  --out outputs_final/cogvideox \
  --batch-size 1
```

Evaluate the CogVideoX outputs separately first:

```bash
python3 scripts/evaluate_outputs.py --runs outputs_final/cogvideox/runs --out analysis/cogvideox/eval
python3 scripts/pareto_select.py --metrics analysis/cogvideox/eval/metrics.csv --out analysis/cogvideox/eval
python3 scripts/train_predictor.py --metrics analysis/cogvideox/eval/metrics.csv --out analysis/cogvideox/predictor.json
python3 scripts/make_progress_report.py --eval analysis/cogvideox/eval --out analysis/cogvideox
python3 scripts/make_frame_grid.py --runs outputs_final/cogvideox/runs --out analysis/cogvideox/frame_grid.svg
```

## Model Comparison

After both model sweeps are evaluated, combine the metrics into `analysis/model_comparison/metrics.csv`. That folder is for cross-model tables, plots, the shared predictor, and scheduler traces.

## What To Show

- A table with one row per real model/config/prompt run.
- The latency-quality plot from `analysis/model_comparison/plots/latency_quality.svg`.
- One frame grid or screenshot grid of the generated videos.
- A short comparison: fast LTX preset vs quality LTX preset vs fast/quality CogVideoX runs.
- A note that last week’s no-GPU outputs were only useful for debugging the evaluator, not for final model quality.

## If A Run Fails

- If there is an out-of-memory error, rerun only `ltx_fast_384x640_49f_20s`.
- If LTX quality is bad, use the `ltx_quality_512x704_81f_30s` config and keep prompts descriptive, photorealistic, and explicit about stable camera motion.
- If CogVideoX is too slow, report LTX as the main real backend and CogVideoX as an integrated but not fully profiled backend.
