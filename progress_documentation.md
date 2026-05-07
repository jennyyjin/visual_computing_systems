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
- A report script that writes `outputs/results.md` and `outputs/latency_quality.svg`

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

## Run Commands 
```bash
python3 scripts/generate_dummy_videos.py --out outputs
python3 scripts/evaluate_outputs.py --runs outputs/runs --manifest outputs/manifest.csv --out outputs/eval
python3 scripts/pareto_select.py --metrics outputs/eval/metrics.csv --out outputs/eval
python3 scripts/make_progress_report.py --eval outputs/eval --out outputs
python3 scripts/train_predictor.py --metrics outputs/eval/metrics.csv --out outputs/predictor.json
python3 scripts/schedule_config.py --predictor outputs/predictor.json --candidates outputs/eval/metrics.csv --budget 0.5 --prompt-id fast_action --out outputs/scheduler_trace.json
```

## Expected Outputs
- `outputs/manifest.csv`
- `outputs/eval/metrics.csv`
- `outputs/eval/pareto_frontier.csv`
- `outputs/eval/budget_selections.csv`
- `outputs/results.md`
- `outputs/latency_quality.svg`
- `outputs/predictor.json`
- `outputs/scheduler_trace.json`

## Next Steps
1. Run the same pipeline on a real video generation backend
2. Add a small real-model profiling sweep
3. Compare default, fast, uniform-scaling, and V-Scale selections
4. Add better prompt-alignment or video-quality metrics if time allows
