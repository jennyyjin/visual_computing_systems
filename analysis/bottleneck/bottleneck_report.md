# Bottleneck Report

## Claim

The main latency driver in our runs is denoising work over frames and pixels. For CogVideoX, CPU offload adds a separate memory-latency bottleneck: it lowers GPU memory use, but slows inference.

We identify bottlenecks at the serving/configuration level, not by changing model kernels. A factor counts as a bottleneck here if changing it while holding the rest of the setup fixed produces a large, predictable latency change.

## Method

We use controlled sweeps. In each experiment, one variable changes and the major remaining settings stay fixed:

- denoising steps
- frame count
- resolution / pixel count
- offload mode

We also check whether a simple work estimate explains latency:

```text
work_units = steps x width x height x frames
```

## 1. Denoising Steps

Model, prompt, resolution, and frame count are fixed. Only denoising steps change.

| Model | Prompt | Fixed setting | Step range | Latency change | Slope |
| --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 768x480, 49 frames | 15 -> 50 | +62.648s | 1.790 s/step |
| CogVideoX-2B | walking person | 768x480, 49 frames | 15 -> 50 | +60.854s | 1.743 s/step |
| CogVideoX-2B | static landscape | 768x480, 49 frames | 15 -> 50 | +56.472s | 1.623 s/step |
| LTX-Video | fast action | 640x384, 49 frames | 4 -> 30 | +2.667s | 0.103 s/step |
| LTX-Video | walking person | 640x384, 49 frames | 4 -> 30 | +2.643s | 0.102 s/step |
| LTX-Video | static landscape | 640x384, 49 frames | 4 -> 30 | +2.572s | 0.099 s/step |

**Interpretation.** Denoising steps have a consistent latency cost. CogVideoX costs about 1.6-1.8 seconds per additional step in this setup, while LTX costs about 0.1 seconds per step. This explains why CogVideoX becomes expensive quickly under latency budgets.

## 2. Frame Count

Model, prompt, denoising steps, and resolution are fixed. Only frame count changes.

| Model | Prompt | Fixed setting | Frame range | Latency change | Slope |
| --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 768x480, 15 steps | 17 -> 81 | +55.183s | 0.875 s/frame |
| CogVideoX-2B | walking person | 768x480, 15 steps | 17 -> 81 | +56.869s | 0.894 s/frame |
| CogVideoX-2B | static landscape | 768x480, 15 steps | 17 -> 81 | +59.780s | 0.953 s/frame |
| LTX-Video | fast action | 640x384, 20 steps | 17 -> 81 | +3.069s | 0.048 s/frame |
| LTX-Video | walking person | 640x384, 20 steps | 17 -> 81 | +3.057s | 0.048 s/frame |
| LTX-Video | static landscape | 640x384, 20 steps | 17 -> 81 | +2.625s | 0.042 s/frame |

**Interpretation.** More frames increase the amount of temporal data processed during denoising. CogVideoX again has a much higher per-unit cost than LTX. The quality proxy does not always improve when frames increase, so the largest frame count under budget is not always the best choice.

## 3. Resolution

Model, prompt, denoising steps, and frame count are fixed. Only pixel count changes.

| Model | Prompt | Fixed setting | Pixel change | Latency change | Latency ratio |
| --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 15 steps, 49 frames | 0.246 -> 0.369 MP | +13.302s | 1.53x |
| CogVideoX-2B | walking person | 15 steps, 49 frames | 0.246 -> 0.369 MP | +13.908s | 1.55x |
| CogVideoX-2B | static landscape | 15 steps, 49 frames | 0.246 -> 0.369 MP | +10.032s | 1.30x |
| LTX-Video | fast action | 20 steps, 49 frames | 0.246 -> 0.360 MP | +1.350s | 1.56x |
| LTX-Video | walking person | 20 steps, 49 frames | 0.246 -> 0.360 MP | +1.342s | 1.56x |
| LTX-Video | static landscape | 20 steps, 49 frames | 0.246 -> 0.360 MP | +1.359s | 1.57x |

**Interpretation.** Increasing resolution raises latency by about 1.3-1.6x. This supports the same bottleneck pattern: latency depends on repeated computation over spatial and temporal data.

## 4. Work-Unit Correlation

The work estimate `steps x width x height x frames` has high correlation with latency:

| Model | corr(latency, work_units) |
| --- | ---: |
| CogVideoX-2B | 0.970 |
| LTX-Video | 0.997 |

**Interpretation.** The correlation does not identify a specific CUDA kernel, but it does show that serving-level latency is largely explained by denoising work. This is enough for the scheduler, because it schedules configurations rather than rewriting kernels.

## 5. Lightweight Predictor

We trained a regularized linear regression predictor using model/configuration features.

| Target | R2 |
| --- | ---: |
| latency | 0.9984 |
| quality proxy | 0.6154 |

**Interpretation.** Latency is highly predictable from model, steps, frames, pixels, and related work features. Quality is noisier, so V-Scale uses measured Pareto frontiers for final scheduling decisions instead of relying only on predicted quality.

## 6. CPU-Offload Ablation

Same CogVideoX prompt and generation settings; only offload mode changes.

Fixed settings:

- prompt: `fast_action`
- steps: 15
- resolution: 768x480
- frames: 17
- precision: fp16

| Offload mode | Latency | Peak memory | Quality proxy |
| --- | ---: | ---: | ---: |
| model CPU offload | 15.587001s | 11066.21 MB | 0.7125 |
| no offload | 9.833798s | 18803.67 MB | 0.7125 |

No offload is 1.59x faster, but uses 1.70x more GPU memory.

**Interpretation.** Offload mode changes latency and memory while leaving the quality proxy unchanged. This makes CPU offload a memory-latency tradeoff: it reduces memory pressure, but adds transfer/execution overhead.

## Scheduler Implications

- Tight latency budgets: prefer lower denoising work, often LTX.
- Extra compute: spend it only when measured quality improves.
- CogVideoX: consider it for high-budget prompts where the quality gain justifies the latency.
- Memory-constrained CogVideoX: use offload when needed, but account for the latency cost.

## Conclusion

The measured bottlenecks are not isolated tuning knobs. Steps, frames, and resolution all increase the same underlying work: repeated denoising over spatial-temporal data. CogVideoX has a much higher per-unit cost than LTX in this sweep, and CPU offload adds a separate memory-latency tradeoff.

This explains why fixed presets are weak baselines. A preset commits to one point in the tradeoff space, while V-Scale selects the best valid point under the current prompt, latency budget, and memory constraint. In the final fixed-preset comparison, V-Scale achieved 17 wins, 1 tie, and 0 losses across the 18 prompt-budget cases where a fixed preset fit the budget.
