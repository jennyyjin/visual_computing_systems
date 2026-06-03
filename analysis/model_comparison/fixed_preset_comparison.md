# Fixed Preset Comparison

This table compares the budget-aware scheduler against a small set of fixed presets:

- `fixed_ltx_preview`: `ltx_fast_384x640_49f_20s`
- `fixed_ltx_quality`: `ltx_quality_512x704_81f_30s`
- `fixed_cogvideox_preview`: `cogvideox_480x768_17f_15s`
- `fixed_cogvideox_quality`: `cogvideox_480x768_49f_50s`

A fixed preset only counts if it produces a valid video under the same latency budget.

## Summary

- Scheduler comparisons: 24 prompt-budget cases
- Cases where no fixed preset fits the budget: 6
- Cases where scheduler beats the best fitting fixed preset: 17
- Cases where scheduler ties the best fitting fixed preset: 1
- Mean quality gain over fitting fixed presets: 0.0549

## Representative Cases

| Prompt | Budget | Scheduler choice | Scheduler quality | Best fixed preset | Fixed quality | Gain |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| fast action | 1.0s | LTX-Video / `ltx_fast_384x640_17f_20s` | 0.4944 | none fits | n/a | n/a |
| fast action | 2.0s | LTX-Video / `ltx_fast_384x640_33f_20s` | 0.5889 | none fits | n/a | n/a |
| fast action | 5.0s | LTX-Video / `ltx_fast_384x640_81f_20s` | 0.6513 | fixed_ltx_preview | 0.5868 | 0.0645 |
| fast action | 20.0s | CogVideoX-2B / `cogvideox_480x768_17f_15s` | 0.7125 | fixed_cogvideox_preview | 0.7125 | 0.0000 |
| fast action | 40.0s | CogVideoX-2B / `cogvideox_384x640_49f_15s` | 0.7685 | fixed_cogvideox_preview | 0.7125 | 0.0560 |
| static landscape | 1.0s | LTX-Video / `ltx_fast_384x640_49f_4s` | 0.5065 | none fits | n/a | n/a |
| static landscape | 2.0s | LTX-Video / `ltx_fast_384x640_33f_20s` | 0.5664 | none fits | n/a | n/a |
| static landscape | 5.0s | LTX-Video / `ltx_fast_384x640_33f_20s` | 0.5664 | fixed_ltx_preview | 0.5155 | 0.0509 |
| static landscape | 20.0s | LTX-Video / `ltx_fast_384x640_33f_20s` | 0.5664 | fixed_ltx_preview | 0.5155 | 0.0509 |
| static landscape | 40.0s | LTX-Video / `ltx_fast_384x640_33f_20s` | 0.5664 | fixed_ltx_preview | 0.5155 | 0.0509 |
| walking person | 1.0s | LTX-Video / `ltx_fast_384x640_17f_20s` | 0.7320 | none fits | n/a | n/a |
| walking person | 2.0s | LTX-Video / `ltx_fast_384x640_49f_15s` | 0.8027 | none fits | n/a | n/a |
| walking person | 5.0s | LTX-Video / `ltx_fast_512x704_49f_20s` | 0.8515 | fixed_ltx_preview | 0.7340 | 0.1175 |
| walking person | 20.0s | LTX-Video / `ltx_fast_512x704_49f_20s` | 0.8515 | fixed_ltx_quality | 0.7906 | 0.0609 |
| walking person | 40.0s | LTX-Video / `ltx_fast_512x704_49f_20s` | 0.8515 | fixed_ltx_quality | 0.7906 | 0.0609 |

## Interpretation

The scheduler helps most when a fixed preset is either over budget or leaves quality on the table. At very low budgets, the fixed full-length presets often do not fit, while the scheduler can choose shorter or lower-step LTX configurations. At higher fast-action budgets, CogVideoX becomes a useful choice because the scheduler can spend more time on motion quality.
