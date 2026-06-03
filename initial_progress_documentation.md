# Progress Documentation 

## Project Question
Can V-Scale choose better video generation settings than fixed presets under the same latency or memory budget?

## Current Focus
For this update, we focused on the measurement pipeline rather than the final scheduling method. The goal is to make sure we can generate outputs, log metadata, score the results, and produce basic plots before spending GPU time on real models. 

## What Is Implemented
- A fixed prompt suite with spatial-detail, medium-motion, and fast-action prompts
- A small configuration sweep over steps, resolution, and frame count
- Dummy video baselines: white, black, static frame, random noise, and moving square
- A shared run format with `metadata.json` and frame directories
- Evaluation metrics for nonblankness, motion, sharpness, stability, and a simple quality proxy
- Pareto frontier and budget-selection scripts
- A lightweight predictor and scheduler trace script
- A report script that writes `analysis/results.md` and `analysis/latency_quality.svg`

## Model Selection
We are using the same evaluation harness for dummy outputs and real video generation backends.

- **Dummy backend:** used to validate the end-to-end pipeline without requiring GPU inference. It provides controlled failure cases such as blank outputs, static frames, random noise, and simple coherent motion, allowing us to verify that the evaluation metrics and scheduler correctly distinguish invalid outputs from usable generations 
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
The dummy backend runs 45 videos:

```text
3 prompts x 3 configs x 5 dummy baselines = 45 runs
```

The expected behavior is:
- blank videos fail
- static videos fail
- random noise fails
- moving-square videos pass

This gives us a basic sanity check for the evaluator before using real video model outputs.

The current repo satisfies the base-case requirement: the full analysis pipeline can run without optimization and produces metrics, a Pareto frontier, budget selections, a predictor file, a scheduler trace, and a quality-latency plot.

## Run Commands 
```bash
python3 scripts/generate_dummy_videos.py --out outputs_final
python3 scripts/evaluate_outputs.py --runs outputs_final/runs --manifest outputs_final/manifest.csv --out analysis/eval
python3 scripts/pareto_select.py --metrics analysis/eval/metrics.csv --out analysis/eval
python3 scripts/make_progress_report.py --eval analysis/eval --out analysis
python3 scripts/train_predictor.py --metrics analysis/eval/metrics.csv --out analysis/predictor.json
python3 scripts/schedule_config.py --predictor analysis/predictor.json --candidates analysis/eval/metrics.csv --budget 0.5 --prompt-id fast_action --out analysis/scheduler_trace.json
```

## Generated Artifacts
- `outputs_final/manifest.csv`
- `analysis/eval/metrics.csv`
- `analysis/eval/pareto_frontier.csv`
- `analysis/eval/budget_selections.csv`
- `analysis/results.md`
- `analysis/latency_quality.svg`
- `analysis/predictor.json`
- `analysis/scheduler_trace.json`

## Remaining Work
1. Run the same pipeline on a real video generation backend
2. Add a small real-model profiling sweep
3. Compare default, fast, uniform-scaling, and V-Scale selections
4. Add better prompt-alignment or video-quality metrics if time allows
