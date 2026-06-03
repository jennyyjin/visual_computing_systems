# V-Scale: Budget-Aware Inference Scheduling for Video Generation

## Team
Jenny Jin (yqjin)  
Jeffrey Liu (liujy3)

## Summary
V-Scale is a serving-layer system for interactive video generation. Given a text prompt and a latency or memory budget, it selects generation settings such as denoising steps, resolution, frame count, precision, guidance scale, and offload mode.

The goal is not only to benchmark model speed but also to use profiling data to make better runtime decisions: generate the best usable video preview under a fixed budget, and compare that decision against fixed presets on the same hardware.

The final evaluation profiles two open-source video generation models, builds quality-latency tradeoff curves, trains lightweight latency/quality predictors, and compares V-Scale against fixed presets under matched budgets.

## Project Question
Can a hardware-aware scheduler choose video generation configurations that produce better outputs than fixed presets while satisfying latency and memory constraints?

## Motivation
Video generation models expose many low-level controls, but interactive users usually care about higher-level constraints: how quickly a preview appears and whether it is usable. The relationship between model settings and runtime is nonlinear and hardware-dependent, especially when resolution, frame count, denoising steps, attention cost, decoding, and memory pressure interact.

The goal of V-Scale is to make video generation more like a controllable inference service. Instead of manually tuning parameters, the system profiles what a backend can do and chooses a configuration that fits the requested budget.

## Inputs And Outputs
### Inputs
- Text prompt
- Latency budget
- Optional memory budget
- Model backend
- Candidate generation settings: denoising steps, width, height, frames, precision, guidance scale, and offload mode

### Outputs
- Selected generation configuration
- Generated video
- Scheduler trace explaining the selected configuration
- Per-run metadata with prompt, model, config, latency, memory, output path, and failure status
- Evaluation artifacts: metrics CSVs, Pareto frontiers, plots, and side-by-side comparisons

## Repository Organization
- `outputs_final/`: raw generated run artifacts from the final experiments, including manifests, videos, frames, and per-run metadata
- `analysis/`: derived metrics, Pareto frontiers, plots, reports, predictor outputs, and comparison tables
- `scripts/`: generation, evaluation, plotting, scheduling, and reporting scripts
- `configs/`: prompt and sweep configuration files
- `slides/`: final presentation source and slide assets
- `outputs/`, `outputs_v2/`: older archived raw experiment outputs kept for provenance
- `analysis/bottleneck/`: bottleneck experiment notes and report
- `analysis/optimization/`: implementation optimization report
- `analysis/outputs/`, `analysis/outputs_v2/`: derived analysis artifacts from the older archived runs

## Constraints
- We do not train a video generation model from scratch.
- The main constraint is limited GPU compute and memory.
- The system supports multiple model backends through adapters.
- Experiments use short clips and modest resolutions so the profiling sweep remains feasible.

## Model Selection
We use a small set of backends selected for feasibility and coverage:
- **Dummy backend:** used to validate the evaluation pipeline without requiring GPU inference. It provides controlled failure cases such as blank outputs, static frames, random noise, and simple coherent motion so we can verify that the evaluator and scheduler correctly distinguish unusable outputs from valid generations 
- **CogVideoX-2B:** primary real-model backend. It integrates cleanly with Diffusers, is relatively lightweight to run, and exposes the main inference controls we want to study, including denoising steps, frame count, resolution, and guidance scale
- **LTX-Video:** secondary backend for cross-model evaluation. It is designed for relatively fast inference and low-step generation, making it a useful contrast to CogVideoX-2B when studying latency-quality tradeoffs and scheduler behavior across different model architectures 

## Prompt Suite
The evaluation prompts are fixed in `configs/prompts.json`:
- `static_landscape`: low motion, spatial-detail focused
- `walking_person`: medium motion, temporal-consistency focused
- `fast_action`: high motion, motion focused
These prompts are intentionally small but cover the main tradeoffs V-Scale needs to handle.

## Approach
### Model Adapter
Each backend exposes a shared generation interface and saves outputs in a common format. This keeps the profiler and evaluator independent of the specific video model.

### Profiler
The profiler runs a bounded sweep over generation settings and logs latency, memory, output path, prompt, model backend, and failure reason. These measurements are the basis for scheduling.

### Evaluator
The evaluator checks whether the output is nonblank, whether frames change over time, whether the video is too noisy, and whether it meets the latency budget. The final quality proxy combines nonblankness, motion, sharpness, and stability.

### Predictor
V-Scale trains lightweight predictors from profiling data. The predictor estimates latency and quality from features such as steps, resolution, frames, precision, offload mode, prompt category, and model backend.

### Scheduler
The scheduler chooses the best valid configuration that satisfies the latency and memory budget. It uses the measured Pareto frontier from profiled runs, with predictor outputs used to summarize how configuration features explain latency and quality.

## Baselines
We compare against:
1. Model default preset
2. Naive fast preset
3. Uniform scaling of parameters until the budget is met
4. Best observed profiled configuration under budget
5. V-Scale scheduler
We also include deliberately bad controls, such as blank, static, and random-noise videos, to verify that the evaluator catches trivial failures.

## Implemented Components
1. Measurement harness with dummy outputs, metadata, metrics, Pareto selection, and plots
2. Real-model backends for LTX-Video and CogVideoX-2B
3. Profiling sweep over steps, frames, resolution, precision, and offload mode
4. Lightweight latency and quality predictors trained from profiling data
5. Budget-aware scheduler
6. Fixed-preset comparison and bottleneck analysis

## Evaluation
We evaluate:
- mean and p95 latency
- peak GPU memory when available
- budget error
- output validity
- quality proxy
The final figures and tables include:
- quality-latency Pareto curve
- fixed-preset comparison table
- predictor summary
- bottleneck analysis
- CPU-offload ablation
- prompt examples and qualitative frames

## Definition Of Success
The project succeeds if the end-to-end system profiles video generation runs, builds a useful quality-latency frontier, predicts latency well enough to support budget-aware scheduling, and selects configurations that improve quality over fixed presets under matched budgets.

## Final Results

Generated run artifacts are in `outputs_final/`; analysis reports, metrics, and plots are in `analysis/`.

V-Scale profiles real LTX-Video and CogVideoX-2B generations on the same Modal L40S GPU, evaluates validity and quality, builds Pareto frontiers, and schedules the best valid configuration under each prompt-budget case.

### Evaluation Snapshot
| Item | Result |
|---|---:|
| Profiled video runs | 54 |
| Valid video runs | 54 |
| Prompt-budget scheduling decisions | 24 |
| Decisions with a fitting fixed-preset baseline | 18 |
| V-Scale wins / ties / losses | 17 / 1 / 0 |
| Mean quality gain over best fitting preset | +0.0549 |

### Main Findings
- Latency and memory constraints change which model/configuration is competitive.
- Denoising work over steps, frames, and pixels is the main latency driver.
- CogVideoX CPU offload reduces GPU memory use but increases latency.
- Most valid configurations are dominated once latency and quality are evaluated jointly.
- Within the measured configuration space, V-Scale outperforms fixed presets by adapting to prompt and budget.

### Key Artifacts
- Final merged metrics: `analysis/model_comparison/metrics.csv`
- Fixed-preset comparison: `analysis/model_comparison/fixed_preset_comparison.csv`
- Prompt-budget scheduler decisions: `analysis/model_comparison/prompt_budget_selections.csv`
- Bottleneck analysis: `analysis/bottleneck/bottleneck_experiments.md`
- CPU-offload ablation: `analysis/offload_test/offload_comparison.md`
- Final presentation source: `slides/vscale_final_current_data.md`

## Risks
### Limited Compute
Some video models may exceed available GPU memory. The backend is flexible, uses short clips and modest resolutions, and treats failed configurations as useful profiling data.

### Noisy Quality Metrics
Automated video metrics may not match human judgment. The current evaluator uses sanity checks and a simple quality proxy, so claims are limited to the measured proxy rather than subjective visual quality.

### Runtime Variance
Latency can vary across repeated runs. The final analysis uses measured profiling data and treats large latency differences as stronger evidence than small differences.

### Predictor Overfitting
The profiling table is small. Scheduler claims are therefore kept inside the profiled configuration space rather than extrapolated to unseen model settings.

## References
- HuggingFace Diffusers: Video generation: https://huggingface.co/docs/diffusers/v0.33.1/en/using-diffusers/text-img2vid
- HuggingFace Diffusers: Memory optimization: https://huggingface.co/docs/diffusers/en/optimization/memory
- OpenAI CLIP: https://openai.com/research/clip
- CLIP code: https://github.com/openai/CLIP
- DOVER: Disentangled Objective Video Quality Evaluator: https://github.com/VQAssessment/DOVER
- VBench: Comprehensive Benchmark Suite for Video Generative Models: https://huggingface.co/papers/2311.17982
- VBench++: Comprehensive and Versatile Benchmark Suite for Video Generative Models: https://huggingface.co/papers/2411.13503
