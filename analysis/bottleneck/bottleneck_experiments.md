# Bottleneck Experiments

Controlled sweeps from `outputs_final`. In each sweep, one variable changes while the model, prompt, and remaining generation settings stay fixed.

## Summary

Latency is mainly driven by denoising work over frames and pixels. CogVideoX has much higher per-step and per-frame cost than LTX in our setup. CPU offload creates a separate memory-latency tradeoff for CogVideoX.

## 1. Denoising Steps

Only denoising steps change.

| Model | Prompt | Fixed setting | Range | Latency change | Slope | Quality change |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 768x480, 49 frames | 15->50 | +62.648s | 1.790 s/step | +0.1766 |
| CogVideoX-2B | static landscape | 768x480, 49 frames | 15->50 | +56.472s | 1.623 s/step | +0.0158 |
| CogVideoX-2B | walking person | 768x480, 49 frames | 15->50 | +60.854s | 1.743 s/step | +0.1725 |
| LTX-Video | fast action | 640x384, 49 frames | 4->30 | +2.667s | 0.103 s/step | +0.3453 |
| LTX-Video | static landscape | 640x384, 49 frames | 4->30 | +2.572s | 0.099 s/step | +0.0124 |
| LTX-Video | walking person | 640x384, 49 frames | 4->30 | +2.643s | 0.102 s/step | +0.2078 |

Takeaway: denoising steps have a large and predictable latency cost. CogVideoX pays roughly 16-18x more per step than LTX.

## 2. Frame Count

Only frame count changes.

| Model | Prompt | Fixed setting | Range | Latency change | Slope | Quality change |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 768x480, 15 steps | 17->81 | +55.183s | 0.875 s/frame | -0.1976 |
| CogVideoX-2B | static landscape | 768x480, 15 steps | 17->81 | +59.780s | 0.953 s/frame | -0.0058 |
| CogVideoX-2B | walking person | 768x480, 15 steps | 17->81 | +56.869s | 0.894 s/frame | -0.1201 |
| LTX-Video | fast action | 640x384, 20 steps | 17->81 | +3.069s | 0.048 s/frame | +0.1569 |
| LTX-Video | static landscape | 640x384, 20 steps | 17->81 | +2.625s | 0.042 s/frame | +0.0000 |
| LTX-Video | walking person | 640x384, 20 steps | 17->81 | +3.057s | 0.048 s/frame | +0.0576 |

Takeaway: more frames increase latency, but extra frames do not always improve the quality proxy. This is why scheduling from measured data is more useful than simply choosing the largest config under budget.

## 3. Resolution

Steps and frame count stay fixed; only pixel count changes.

| Model | Prompt | Fixed setting | Pixel change | Latency change | Latency ratio | Quality change |
| --- | --- | --- | --- | ---: | ---: | ---: |
| CogVideoX-2B | fast action | 15 steps, 49 frames | 0.246->0.369 MP | +13.302s | 1.53x | -0.1229 |
| CogVideoX-2B | static landscape | 15 steps, 49 frames | 0.246->0.369 MP | +10.032s | 1.30x | -0.0040 |
| CogVideoX-2B | walking person | 15 steps, 49 frames | 0.246->0.369 MP | +13.908s | 1.55x | -0.0347 |
| LTX-Video | fast action | 20 steps, 49 frames | 0.246->0.360 MP | +1.350s | 1.56x | +0.0264 |
| LTX-Video | static landscape | 20 steps, 49 frames | 0.246->0.360 MP | +1.359s | 1.57x | -0.0144 |
| LTX-Video | walking person | 20 steps, 49 frames | 0.246->0.360 MP | +1.342s | 1.56x | +0.1175 |

Takeaway: resolution scales latency by about 1.3-1.6x in these comparisons. Higher resolution helps some prompts, but not all.

## 4. Work-Unit Check

We use a simple work estimate:

```text
work_units = steps x width x height x frames
```

| Model | corr(latency, work_units) |
| --- | ---: |
| CogVideoX-2B | 0.970 |
| LTX-Video | 0.997 |

Takeaway: this simple term explains most latency variation in the profiled sweep, which supports the denoising-work bottleneck claim.

## 5. CogVideoX Offload Ablation

Same CogVideoX prompt and generation settings; only offload mode changes.

| Offload mode | Latency | Peak memory | Quality proxy | Valid |
| --- | ---: | ---: | ---: | --- |
| model CPU offload | 15.587001s | 11066.21 MB | 0.7125 | yes |
| no offload | 9.833798s | 18803.67 MB | 0.7125 | yes |

No offload is 1.59x faster, but uses 1.70x more GPU memory.

Takeaway: CPU offload is not a quality tradeoff in this run; it is a memory-latency tradeoff. It makes CogVideoX feasible at lower memory, but slows inference.

## Scheduling Implication

V-Scale should spend denoising work only when the measured quality gain justifies the latency. Under tight budgets this often favors LTX. CogVideoX becomes useful only when the budget is large enough and the prompt benefits from its higher-quality motion result.
