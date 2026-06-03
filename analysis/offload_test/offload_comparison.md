# CogVideoX Offload Comparison

This experiment tests whether CPU offload is part of the CogVideoX latency bottleneck.

The two runs use the same prompt and generation settings:

- prompt: `fast_action`
- model: `THUDM/CogVideoX-2b`
- steps: 15
- resolution: 768x480
- frames: 17
- precision: fp16

| Offload mode | Latency | Peak memory | Quality proxy | Valid |
| --- | ---: | ---: | ---: | --- |
| model CPU offload | 15.587001s | 11066.21 MB | 0.7125 | yes |
| no offload | 9.833798s | 18803.67 MB | 0.7125 | yes |

The no-offload run is 1.59x faster, but uses 1.70x more GPU memory.

Interpretation: CPU offload is a real part of the CogVideoX latency bottleneck in our setup. It reduces GPU memory pressure, but the model pays for this with slower inference. This supports the broader bottleneck story: video generation latency is dominated by denoising work, and memory-management choices can add extra overhead on top of that work.
