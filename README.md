# V-Scale: Budget-Aware Inference Scheduling for Video Generation

Stanford CS348K, Visual Computing Systems, Spring 2026  
Jenny Jin (`yqjin`) and Jeffrey Liu (`liujy3`)

## Overview

V-Scale is a small profiling and scheduling system for text-to-video generation. Given a prompt and a latency or memory budget, it chooses the best measured model/configuration that fits the budget.

The main question we looked at was:

> How do latency and memory constraints change the comparison of video generation models and configurations, and can a budget-aware scheduler use these tradeoffs to improve delivered quality over fixed presets?

**Full report:** [final_report.pdf](final_report.pdf) contains the complete problem definition, method, pipeline, results, bottleneck analysis, and discussion.

We compare LTX-Video and CogVideoX-2B on the same Modal L40S GPU. For each model, we sweep settings such as denoising steps, frame count, resolution, precision, and CPU offload mode. We then use the measured results to decide which configuration should be served under a given budget.

## Key Results

| Result | Value |
| --- | ---: |
| Profiled video runs | 54 |
| Valid video runs | 54 |
| Prompt-budget scheduling decisions | 24 |
| Decisions with a fitting fixed-preset baseline | 18 |
| V-Scale wins / ties / losses | 17 / 1 / 0 |
| Mean quality gain over best fitting fixed preset | +0.0549 |

Main findings:

- Latency constraints change which configurations are competitive: 49 of 54 profiled configurations are dominated once latency and quality are considered together.
- Denoising work is the main latency driver. The estimated work term `steps x width x height x frames` correlates strongly with latency for both CogVideoX-2B and LTX-Video.
- CPU offload creates a memory-latency tradeoff. In the CogVideoX ablation, offload reduced peak GPU memory from 18.8 GB to 11.1 GB, but increased latency from 16.5 s to 22.1 s on average.
- Fixed presets can be misleading because they commit to one point in the tradeoff space. V-Scale adapts the model/configuration choice to the prompt and budget.

## System

V-Scale has four stages:

1. **Profile** model/configuration runs on fixed hardware.
2. **Evaluate** each generated video for validity, latency, memory, and a simple quality proxy.
3. **Analyze** Pareto frontiers, bottlenecks, and predictor fit.
4. **Schedule** the highest-quality valid configuration under the requested budget.

Formally, for prompt `p`, latency budget `B`, hardware `H`, and candidate set `C`, V-Scale selects:

```text
c* = argmax quality(c)
     subject to latency(c, H) <= B
```

When memory is constrained, the selected configuration must also fit the available GPU memory.

## Inputs And Outputs

Inputs:

- text prompt
- latency budget
- optional memory constraint
- hardware target
- candidate model/configuration set

Outputs:

- selected model/configuration
- generated video and run metadata
- latency and peak-memory measurements
- validity and quality metrics
- Pareto frontier and budget-selection tables

## Prompt Suite

The final evaluation uses three fixed prompts in `configs/prompts.json`:

- `static_landscape`: low motion, spatial detail
- `walking_person`: medium motion, temporal consistency
- `fast_action`: high motion, motion quality

These prompts are intentionally small. They cover different behavior: static detail, ordinary motion, and faster motion.

## Evaluation Metrics

The evaluator writes one row per generated run. The main fields are:

- `latency_seconds`: end-to-end generation time
- `peak_memory_mb`: peak GPU memory when available
- `spatial_std`: contrast / nonblankness check
- `temporal_delta`: frame-to-frame change
- `sharpness_score`: local image variation
- `stability_score`: penalty for excessive flicker/noise
- `quality_proxy`: reference-free score used for scheduling comparisons
- `valid_video`: validity gate for blank, static, or noisy outputs

The quality proxy is not meant to replace human judgment. We use it as a consistent metric for comparing runs inside this profiled sweep.

## Repository Organization

- `configs/`: prompt and sweep configuration files
- `scripts/`: generation, evaluation, scheduling, plotting, and analysis scripts
- `analysis/`: derived metrics, Pareto frontiers, predictor outputs, plots, and reports
- `analysis/model_comparison/`: final cross-model metrics and scheduler comparisons
- `analysis/bottleneck/`: controlled bottleneck experiments and report
- `analysis/offload_test/`: CogVideoX CPU-offload ablation
- `analysis/optimization/`: implementation optimization notes
- `outputs_final/`: final generated run artifacts when present locally
- `outputs/`, `outputs_v2/`: archived earlier runs kept for provenance

Large generated frame directories are not needed for the analysis tables and can be kept outside Git. The results used in the report are summarized in `analysis/`.

## Important Artifacts

- Final merged metrics: `analysis/model_comparison/metrics.csv`
- Pareto frontier: `analysis/model_comparison/pareto_frontier.csv`
- Prompt-budget selections: `analysis/model_comparison/prompt_budget_selections.csv`
- Fixed-preset comparison: `analysis/model_comparison/fixed_preset_comparison.md`
- Final results notes: `analysis/model_comparison/final_results_notes.md`
- Bottleneck report: `analysis/bottleneck/bottleneck_report.md`
- Bottleneck experiments: `analysis/bottleneck/bottleneck_experiments.md`
- CPU-offload comparison: `analysis/offload_test/offload_comparison.md`
- Predictor summary: `analysis/model_comparison/predictor.json`

## Reproducing The Analysis

Evaluate a run manifest:

```bash
python3 scripts/evaluate_outputs.py \
  --manifest outputs_final/ltx_video/manifest.csv \
  --out analysis/ltx_video/eval
```

Compute the Pareto frontier and budget selections:

```bash
python3 scripts/pareto_select.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison
```

Train the lightweight predictor:

```bash
python3 scripts/train_predictor.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison/predictor.json
```

Compare V-Scale against fixed presets:

```bash
python3 scripts/compare_fixed_presets.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/model_comparison
```

Generate bottleneck tables:

```bash
python3 scripts/summarize_bottlenecks.py \
  --metrics analysis/model_comparison/metrics.csv \
  --out analysis/bottleneck/bottleneck_experiments.md
```

## Main Scripts

- `scripts/run_modal_video_sweep.py`: run LTX-Video or CogVideoX sweeps on Modal
- `scripts/evaluate_outputs.py`: compute validity and quality metrics
- `scripts/pareto_select.py`: compute Pareto frontier and budget selections
- `scripts/train_predictor.py`: train linear latency and quality predictors
- `scripts/schedule_config.py`: choose a configuration under a latency budget
- `scripts/compare_fixed_presets.py`: compare scheduler choices to fixed presets
- `scripts/analyze_final_results.py`: generate final cross-model analysis artifacts
- `scripts/summarize_bottlenecks.py`: summarize controlled bottleneck sweeps
- `scripts/plot_pareto_dominated.py`: plot dominated configurations and Pareto frontier
- `scripts/plot_offload_tradeoff.py`: plot CPU-offload memory/latency tradeoff

## Limitations

- The sweep is small, so the conclusions are limited to the prompts and configurations we measured.
- The quality metric is a proxy. It is useful for relative comparisons here, but it is not a full perceptual or semantic video metric.
- Latency can vary across runs. We focus on larger differences and controlled one-variable sweeps.
- V-Scale optimizes configuration selection at the serving layer. It does not modify model kernels or train new video models.

## References

- HuggingFace Diffusers video generation documentation: https://huggingface.co/docs/diffusers/v0.33.1/en/using-diffusers/text-img2vid
- HuggingFace Diffusers memory optimization documentation: https://huggingface.co/docs/diffusers/en/optimization/memory
- LTX-Video: https://github.com/Lightricks/LTX-Video
- CogVideoX: https://github.com/THUDM/CogVideo
- VBench: https://huggingface.co/papers/2311.17982
