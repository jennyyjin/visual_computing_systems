# Scripts

The scripts are grouped by the stage of the pipeline.

## Run Generation

- `run_modal_video_sweep.py`: run LTX-Video or CogVideoX sweeps on Modal and download runs.
- `run_cogvideox_diffusers.py`: local CogVideoX helper for a single Diffusers run.
- `record_real_run.py`: import externally generated frames into the project run schema.

## Evaluation And Selection

- `evaluate_outputs.py`: compute validity, latency, memory, and quality-proxy metrics.
- `pareto_select.py`: write Pareto frontier and budget-selection tables from metrics.
- `train_predictor.py`: train the lightweight linear latency/quality predictor.
- `schedule_config.py`: choose a configuration under a latency budget.
- `compare_fixed_presets.py`: compare V-Scale choices against fixed presets.

## Analysis And Figures

- `analyze_final_results.py`: build final cross-model tables and latency plots.
- `summarize_bottlenecks.py`: summarize controlled bottleneck sweeps.
- `make_progress_report.py`: create per-model evaluation summaries.
- `make_frame_grid.py`: create frame-grid SVGs from generated runs.
- `make_prompt_examples.py`: create the prompt example figure.
- `plot_pareto_dominated.py`: create the dominated-configuration Pareto plot.
- `plot_offload_tradeoff.py`: create the CPU-offload memory/latency plot.
