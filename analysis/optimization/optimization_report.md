# Optimization Report

## Scope

V-Scale does not modify model weights or kernels. The optimization is at the serving layer: given a prompt and resource budget, choose the model/configuration that gives the best measured quality while satisfying the constraints.

The scheduler can vary:

- model backend
- denoising steps
- frame count
- resolution
- CPU offload mode

## Bottleneck Behind The Optimization

The bottleneck experiments show that latency is mainly explained by denoising work:

```text
work_units = steps x width x height x frames
```

| Model | corr(latency, work_units) |
| --- | ---: |
| CogVideoX-2B | 0.970 |
| LTX-Video | 0.997 |

CogVideoX also has a memory-latency bottleneck from CPU offload. Offload lowers GPU memory use, but adds latency.

## Optimization 1: Budget-Aware Scheduling

Baseline: choose from fixed presets.

V-Scale: search the measured profile table, keep valid runs under budget, and select the highest measured quality proxy.

| Metric | Result |
| --- | ---: |
| Prompt-budget cases | 24 |
| No fixed preset fit | 6 |
| Scheduler wins | 17 |
| Scheduler ties | 1 |
| Scheduler losses | 0 |
| Mean quality gain over fitting presets | +0.0549 |

Interpretation: fixed presets often miss better budget-specific choices. The scheduler improves quality by adapting to the prompt and latency budget instead of committing to one preset.

## Optimization 2: CPU-Offload Policy

For CogVideoX, we tested the same configurations with and without CPU offload. Only offload mode changed.

| Config | CPU offload latency | No-offload latency | Speedup | CPU offload memory | No-offload memory | Quality change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cogvideox_480x768_17f_15s` | 15.587s | 9.834s | 1.59x | 11066 MB | 18804 MB | +0.0000 |
| `cogvideox_384x640_49f_15s` | 25.229s | 19.573s | 1.29x | 11066 MB | 18780 MB | +0.0000 |
| `cogvideox_480x768_33f_15s` | 25.408s | 20.056s | 1.27x | 11066 MB | 18837 MB | +0.0000 |

Interpretation: disabling offload is faster when enough GPU memory is available, but it costs about 1.70x more peak memory. This is a policy choice, not a free speedup.

## Scheduling Rules From The Measurements

- Tight latency budget: prefer lower denoising work, often LTX.
- Extra budget: spend it only when measured quality improves.
- High-budget fast action: consider CogVideoX when the quality gain justifies the latency.
- Memory-constrained CogVideoX: use CPU offload, but account for the latency overhead.

## Final Claim

V-Scale improves serving decisions by scheduling around measured bottlenecks. In the profiled configuration space, it beats the best fitting fixed preset in 17 of 18 comparable prompt-budget cases, and the offload ablation shows a concrete memory-latency policy for CogVideoX.
