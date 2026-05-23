# V-Scale: Budget-Aware Inference Scheduling for Video Generation

## Team
Jenny Jin (yqjin)  
Jeffrey Liu (liujy3)

## Summary
V-Scale is a serving-layer system for interactive video generation. Given a text prompt and a latency or memory budget, it selects generation settings such as denoising steps, resolution, frame count, precision, guidance scale, and offload mode.

The goal is not only to benchmark model speed but also to use profiling data to make better runtime decisions: generate the best usable video preview under a fixed budget, and show that this beats fixed presets on the same hardware. 

We will evaluate the system by profiling feasible open-source video generation models, building quality-latency tradeoff curves, training lightweight latency/quality predictors, and comparing V-Scale against fixed presets under the same budgets.

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

## Constraints
- We will not train a video generation model from scratch.
- The main constraint is limited GPU compute and memory.
- The system should support multiple model backends through adapters.
- Experiments will start with short clips and modest resolutions so the pipeline remains feasible.

## Model Selection
We will use a small set of backends selected for feasibility and coverage:
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
Each backend will expose a shared generation interface and save outputs in a common format. This keeps the profiler and evaluator independent of the specific video model.

### Profiler
The profiler runs a bounded sweep over generation settings and logs latency, memory, output path, prompt, model backend, and failure reason. These measurements are the basis for the scheduler.

### Evaluator
The evaluator starts with simple sanity checks: whether the output is nonblank, whether frames change over time, whether the video is too noisy, and whether it meets the latency budget. For the final report, we will add prompt-alignment or video-quality metrics where feasible.

### Predictor
V-Scale trains lightweight predictors from profiling data. The predictor estimates latency and quality from features such as steps, resolution, frames, precision, offload mode, prompt category, and model backend.

### Scheduler
The scheduler chooses the best predicted configuration that satisfies the latency and memory budget. The first version uses the Pareto frontier from profiled runs; the stronger version uses the predictor and prompt category to allocate compute differently for motion-heavy and detail-heavy prompts.

## Baselines
We will compare against: 
1. Model default preset
2. Naive fast preset
3. Uniform scaling of parameters until the budget is met
4. Best observed profiled configuration under budget
5. V-Scale scheduler
We also include deliberately bad controls, such as blank, static, and random-noise videos, to verify that the evaluator catches trivial failures.

## Task List
1. Build a runnable measurement harness with dummy outputs, metadata, metrics, Pareto selection, and plots
2. Integrate at least one real video generation backend
3. Run a small profiling sweep over steps, frames, resolution, precision, and guidance scale
4. Train lightweight latency and quality predictors from profiling data
5. Implement the budget-aware scheduler
6. Compare V-Scale against fixed baselines and analyze latency/quality tradeoffs

## Evaluation Plan
We will evaluate:
- mean and p95 latency
- peak GPU memory when available
- budget error
- output validity
- quality proxy
- prompt-alignment or video-quality metrics if feasible
- human pairwise preference on a small set of final videos

Expected figures:
- quality-latency Pareto curve
- budget-compliance plot
- baseline comparison table
- predictor error plot
- compute-allocation heatmap
- side-by-side qualitative demo

## Definition Of Success
The project succeeds if we can show an end-to-end system that profiles video generation runs, builds a useful quality-latency frontier, predicts latency well enough to avoid most budget violations, and selects configurations that improve quality over naive fast presets under matched budgets.

## Intermediate Results

We started with running one model for inferencing end to end to get expected video generation and measure its speed. Then we tried a few configurations to try. Those preliminary results can be found in models directory. After those confirmation with expected results, we scaled up and tried each model with multiple configurations and evaluation metrics recorded.

We have completed an end-to-end evaluation pipeline that:
- profiles generation runs,
- computes validity and quality metrics,
- constructs Pareto frontiers,
- and selects configurations under latency budgets.

Current evaluation results are summarized in `results/evaluation_summary.md`. The output videos and frames can found outputs/cogvideox/runs for the cogvideox model and outputs/ltx_video/runs for the ltx model.

### Current Evaluation Snapshot
- Total evaluated runs: 12
- Valid videos: 11
- Invalid videos: 1
- Pareto frontier points: 2

### Highest-Scoring Valid Run
| Run | Quality Proxy | Latency |
|---|---|---|
| `ltx_walking_person_ltx_fast_384x640_49f_20s` | 0.8534 | 2.43s |

The current best-performing configuration achieves relatively high quality while remaining well under the target latency budgets.

### Validity Outcomes
| Outcome | Count |
|---|---|
| ok | 11 |
| no_temporal_change | 1 |

The evaluator successfully detects trivial failures such as videos with no temporal motion, validating that the metric pipeline can distinguish unusable outputs from valid generations.

### Budget-Constrained Scheduler Selections
| Budget | Selected Run | Quality | Latency |
|---|---|---|---|
| 5s | `ltx_walking_person_ltx_fast_384x640_49f_20s` | 0.8534 | 2.43s |
| 10s | `ltx_walking_person_ltx_fast_384x640_49f_20s` | 0.8534 | 2.43s |
| 45s | `ltx_walking_person_ltx_fast_384x640_49f_20s` | 0.8534 | 2.43s |
| 70s | `ltx_walking_person_ltx_fast_384x640_49f_20s` | 0.8534 | 2.43s |

At the current scale of experiments, the scheduler consistently selects the same Pareto-optimal configuration across all tested budgets because it dominates the available profiled runs.

## What We Have Demonstrated So Far

So far, we have demonstrated:
- an operational profiling and evaluation pipeline,
- automatic detection of invalid outputs,
- Pareto frontier construction,
- budget-aware configuration selection,
- and integration of a real video-generation backend.

These results validate the core infrastructure required for V-Scale.

## Risks
### Limited Compute
Some video models may exceed available GPU memory. We will keep the backend flexible, use short clips and modest resolutions, and treat failed configurations as useful profiling data.

### Noisy Quality Metrics
Automated video metrics may not match human judgment. We will combine simple sanity checks with prompt-alignment metrics and a small human comparison where feasible.

### Runtime Variance
Latency can vary across repeated runs. We will use warmup runs, repeat important frontier candidates, and report p50/p95 latency.

### Predictor Overfitting
The profiling table may be small. We will compare learned predictors against lookup and oracle baselines and avoid extrapolating far outside the profiled region.

## References
- HuggingFace Diffusers: Video generation: https://huggingface.co/docs/diffusers/v0.33.1/en/using-diffusers/text-img2vid
- HuggingFace Diffusers: Memory optimization: https://huggingface.co/docs/diffusers/en/optimization/memory
- OpenAI CLIP: https://openai.com/research/clip
- CLIP code: https://github.com/openai/CLIP
- DOVER: Disentangled Objective Video Quality Evaluator: https://github.com/VQAssessment/DOVER
- VBench: Comprehensive Benchmark Suite for Video Generative Models: https://huggingface.co/papers/2311.17982
- VBench++: Comprehensive and Versatile Benchmark Suite for Video Generative Models: https://huggingface.co/papers/2411.13503
