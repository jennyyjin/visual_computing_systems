# Final Results Notes

## Problem Statement

Given a text prompt and a latency budget, choose a video generation model and inference configuration that produces a valid video with the highest measured quality proxy on the same GPU setup.

Inputs: prompt, latency budget, candidate model/configuration set.
Outputs: selected configuration, generated video, latency/memory measurements, and quality/validity metrics.

## Measured Dataset

- Total profiled runs: 54
- Valid videos: 54
- Invalid videos: 0
- CogVideoX-2B: 24 runs, 24 valid, latency 15.59-101.18s, best quality 0.8222
- LTX-Video: 30 runs, 30 valid, latency 0.78-9.19s, best quality 0.8515

## Predictor

The lightweight predictor is a regularized linear regression over steps, frame count, resolution, estimated work units, model, prompt, config, and precision.
- Training rows: 54
- Latency R2: 0.9984
- Quality R2: 0.6154

## Bottleneck Signals

| Model | corr(latency, steps) | corr(latency, frames) | corr(latency, pixels) | corr(latency, work units) |
| --- | ---: | ---: | ---: | ---: |
| CogVideoX-2B | 0.806 | 0.609 | 0.292 | 0.970 |
| LTX-Video | 0.701 | 0.734 | 0.750 | 0.997 |

Controlled one-variable comparisons:

- CogVideoX-2B: median step slope 1.734 s/step; median frame slope 0.890 s/frame
- LTX-Video: median step slope 0.102 s/step; median frame slope 0.048 s/frame

## Per-Prompt Budget Choices

| Prompt | Budget | Selected model | Latency | Quality | Selected run |
| --- | ---: | --- | ---: | ---: | --- |
| fast action | 1.0s | LTX-Video | 0.983s | 0.4944 | `ltx_fast_action_ltx_fast_384x640_17f_20s` |
| fast action | 2.0s | LTX-Video | 1.735s | 0.5889 | `ltx_fast_action_ltx_fast_384x640_33f_20s` |
| fast action | 5.0s | LTX-Video | 4.052s | 0.6513 | `ltx_fast_action_ltx_fast_384x640_81f_20s` |
| fast action | 10.0s | LTX-Video | 4.052s | 0.6513 | `ltx_fast_action_ltx_fast_384x640_81f_20s` |
| fast action | 20.0s | CogVideoX-2B | 15.587s | 0.7125 | `cogvideox_fast_action_cogvideox_480x768_17f_15s` |
| fast action | 40.0s | CogVideoX-2B | 25.229s | 0.7685 | `cogvideox_fast_action_cogvideox_384x640_49f_15s` |
| fast action | 70.0s | CogVideoX-2B | 25.229s | 0.7685 | `cogvideox_fast_action_cogvideox_384x640_49f_15s` |
| fast action | 100.0s | CogVideoX-2B | 25.229s | 0.7685 | `cogvideox_fast_action_cogvideox_384x640_49f_15s` |
| static landscape | 1.0s | LTX-Video | 0.793s | 0.5065 | `ltx_static_landscape_ltx_fast_384x640_49f_4s` |
| static landscape | 2.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 5.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 10.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 20.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 40.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 70.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| static landscape | 100.0s | LTX-Video | 1.727s | 0.5664 | `ltx_static_landscape_ltx_fast_384x640_33f_20s` |
| walking person | 1.0s | LTX-Video | 0.970s | 0.7320 | `ltx_walking_person_ltx_fast_384x640_17f_20s` |
| walking person | 2.0s | LTX-Video | 1.893s | 0.8027 | `ltx_walking_person_ltx_fast_384x640_49f_15s` |
| walking person | 5.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |
| walking person | 10.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |
| walking person | 20.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |
| walking person | 40.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |
| walking person | 70.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |
| walking person | 100.0s | LTX-Video | 3.742s | 0.8515 | `ltx_walking_person_ltx_fast_512x704_49f_20s` |

## Result Claim

In our measured sweep, profiling plus budget-aware selection improves over fixed model choices by switching between configurations based on the prompt and budget. LTX-Video dominates the low-latency region and the global Pareto frontier, while CogVideoX-2B becomes useful only for the high-budget fast-action case. The strongest current evidence is the measured frontier, per-prompt budget table, and latency scaling analysis.
