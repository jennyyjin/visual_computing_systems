# V-Scale: Budget-Aware Inference Scheduling for Video Generation

## Team
Jenny Jin (yqjin)  
Jeffrey Liu (liujy3)

## Summary
V-Scale is a serving-layer system for interactive video generation. Given a text prompt and a latency or memory budget, it selects generation settings such as denoising steps, resolution, frame count, precision, guidance scale, and offload mode.

We will evaluate the system by profiling feasible open-source video generation models, building quality-latency tradeoff curves, training lightweight latency/quality predictors, and comparing V-Scale against fixed presets under the same budgets.

## Project Question
Can a hardware-aware scheduler choose video generation configurations that produce better outputs than fixed presets while satisfying latency and memory constraints?

## Motivation
Video generation models expose many low-level controls, but interactive users usually care about higher-level constraints: how quickly a preview appears and whether it is usable. The relationship between model settings and runtime is nonlinear and hardware-dependent, especially when resolution, frame count, denoising steps, attention cost, decoding, and memory pressure interact.

The goal of V-Scale is to make video generation more like a controllable inference service. Instead of manually tuning parameters, the system profiles what a backend can do and chooses a configuration that fits the requested budget.

## Inputs And Outputs
### Inputs
- Text prompt.
- Latency budget.
- Optional memory budget.
- Model backend.
- Candidate generation settings: denoising steps, width, height, frames, precision, guidance scale, and offload mode.

### Outputs
- Selected generation configuration.
- Generated video.
- Scheduler trace explaining the selected configuration.
- Per-run metadata with prompt, model, config, latency, memory, output path, and failure status.
- Evaluation artifacts: metrics CSVs, Pareto frontiers, plots, and side-by-side comparisons.

## Constraints
- We will not train a video generation model from scratch.
- The main constraint is limited GPU compute and memory.
- The system should support multiple model backends through adapters.
- Experiments will start with short clips and modest resolutions so the pipeline remains feasible.

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
1. Build a runnable measurement harness with dummy outputs, metadata, metrics, Pareto selection, and plots.
2. Integrate at least one real video generation backend.
3. Run a small profiling sweep over steps, frames, resolution, precision, and guidance scale.
4. Train lightweight latency and quality predictors from profiling data.
5. Implement the budget-aware scheduler.
6. Compare V-Scale against fixed baselines and analyze latency/quality tradeoffs.

## Evaluation Plan
We will evaluate:
- mean and p95 latency,
- peak GPU memory when available,
- budget error,
- output validity,
- quality proxy,
- prompt-alignment or video-quality metrics if feasible,
- human pairwise preference on a small set of final videos.

Expected figures:
- quality-latency Pareto curve,
- budget-compliance plot,
- baseline comparison table,
- predictor error plot,
- compute-allocation heatmap,
- side-by-side qualitative demo.

## Definition Of Success
The project succeeds if we can show an end-to-end system that profiles video generation runs, builds a useful quality-latency frontier, predicts latency well enough to avoid most budget violations, and selects configurations that improve quality over naive fast presets under matched budgets.

## Current Progress
Current progress is documented in progress_documentation.md. The current code runs the evaluation pipeline on dummy videos so that the metrics, report generation, Pareto selection, predictor, and scheduler can be tested before running expensive models.

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
