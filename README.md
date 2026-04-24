# visual_computing_systems

## Team
Jenny Jin (yqjin)  
Jeffrey Liu (liujy3)

## Summary
We are going to build a system that benchmarks and optimizes modern video generation models to determine their maximum achievable inference speed under realistic constraints. We will demonstrate success by producing a set of graphs comparing throughput, latency, and quality tradeoffs across models, rather than relying on a single fps metric. Our approach involves systematically applying optimizations (batching, quantization, parallelism) and analyzing bottlenecks to identify the true performance limits of each model.

## Inputs and Outputs

### Inputs
- Pretrained video generation models (e.g., diffusion-based or transformer-based)
- Text prompts or conditioning inputs
- Hardware configuration (GPU type, memory constraints)

### Outputs
- Generated videos
- Performance metrics:
  - Throughput (FPS)
  - Latency per frame / per video
  - GPU utilization
  - Memory usage
- Evaluation plots (e.g., speed vs quality curves)

### Constraints
- GPU compute and memory bandwidth
- Model size and architecture
- Real-time or near real-time latency targets

## Task List

### Core Tasks
#### 1. Baseline Setup
- Select 2–3 representative video generation models
- Download and run models end-to-end
- Verify correct video outputs

#### 2. Benchmarking Framework
- Build a unified pipeline to measure:
  - FPS / throughput
  - Latency breakdown
  - GPU utilization
- Standardize evaluation across all models

#### 3. Optimization Implementation
- Apply optimizations such as:
  - Batching
  - Mixed precision / quantization
  - Resolution scaling
  - Pipeline parallelism
- Compare optimized performance against baseline

#### 4. Bottleneck Analysis
- Profile execution to identify:
  - Compute-bound vs memory-bound behavior
  - Data transfer overhead
- Analyze limiting factors for each model

#### 5. Maximum Performance Analysis
- Vary parameters (batch size, resolution, etc.)
- Identify saturation points where performance plateaus
- Approximate maximum achievable throughput for each model

### Nice-to-Haves
- LLM-based system to suggest optimizations
- Automatic search for best configurations under constraints

## Expected Deliverables and Evaluation

### Deliverables
- Graphs of throughput (FPS) vs batch size / resolution
- Latency breakdown per pipeline stage
- GPU utilization and memory usage plots
- Quality vs speed tradeoff curves

### Evaluation Questions
- Which model achieves the highest throughput under optimized settings?
- What are the main bottlenecks limiting performance?
- When does performance saturate due to hardware constraints?
- How do optimizations affect speed vs quality tradeoffs?

### Success Criteria
- Demonstrate meaningful speedup over baseline implementations
- Show clear saturation behavior (diminishing returns)
- Identify whether systems are compute-bound or memory-bound

## Risks and Mitigation
**Models are difficult to run or too resource-intensive**  
Start with smaller models and scale up  

**Limited performance gains from optimizations**  
Focus on detailed profiling and bottleneck analysis  

**Hardware constraints**  
Use lower resolution or fewer frames for experiments