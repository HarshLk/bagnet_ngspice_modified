# Complementary Class-AB Op-Amp: Custom BagNet Experiment

This document provides an end-to-end reference for the **Complementary Class-AB Op-Amp** experiment added to the BagNet framework. It covers the design rationale, every file created, how to run the optimization, how to customize it, and how to interpret the results.

---

## Table of Contents

1. [How This Experiment Was Built](#1-how-this-experiment-was-built)
2. [Architecture & File Map](#2-architecture--file-map)
3. [Circuit Design & 45nm Adaptation](#3-circuit-design--45nm-adaptation)
4. [How to Run](#4-how-to-run)
5. [How to Customize](#5-how-to-customize)
6. [Outputs, Storage & Interpretation](#6-outputs-storage--interpretation)

---

## 1. How This Experiment Was Built

The experiment was created by following the exact same structure used by the existing `two_stage_opamp` experiment. BagNet requires **four interconnected files** for any new topology:

| # | Component | What It Does | File Created |
|---|-----------|-------------|--------------|
| 1 | **Netlist Templates** (`.cir`) | SPICE circuit with Jinja2 placeholders for the optimizer | 4 files in `bb_envs/src/ngspice/templates/comp_classab/` |
| 2 | **Wrappers** (`.py`) | Parse raw ngspice output into structured metrics | `bb_envs/src/ngspice/wrappers/comp_classab.py` |
| 3 | **Flow** (`.py`) | Coordinates all 4 simulations and computes final specs | `bb_envs/src/ngspice/flows/comp_classab.py` |
| 4 | **Environment YAML** | Defines the design space (parameters) and spec targets | `bb_envs/src/ngspice/envs/comp_classab_opamp.yaml` |
| 5 | **Experiment Specs** (`.yaml`) | Configures the AI agent, DNN model, and EA behavior | 3 files in `specs/iccad/` |

**No existing files were modified.** The `two_stage_opamp` and `cs_amp` experiments remain untouched.

### Step-by-Step Process

1. **Studied the reference implementation** — Read every file in the `two_stage_opamp` pipeline to understand the template → wrapper → flow → YAML → spec chain.
2. **Analyzed the 45nm model** — Checked `bb_envs/src/ngspice/models/45nm_bulk.txt` to confirm device names (`nmos`/`pmos`), threshold voltages (`Vth ≈ ±0.22V`), and appropriate voltage/dimension scaling.
3. **Adapted the user's 180nm netlist** — Converted the original complementary class-AB op-amp from 180nm to 45nm technology (details in [Section 3](#3-circuit-design--45nm-adaptation)).
4. **Created 4 testbench templates** — Open-loop AC, common-mode, power supply rejection, and transient — each with the same stimulus structure as the `two_stage` equivalents.
5. **Created Python wrapper classes** — 4 classes (`CompClassABOpenLoop`, `CompClassABCommonModeGain`, `CompClassABPowerSupplyGain`, `CompClassABTransient`) that parse ngspice CSV output.
6. **Created a flow coordinator** — `CompClassABFlow` runs all 4 testbenches per design and computes gain, UGBW, PM, CMRR, PSRR, settling time, offset, and bias current.
7. **Created the environment YAML** — Defines 13 optimizable parameters and 8 spec targets.
8. **Created 3 experiment spec YAMLs** — For BagNet (DNN+EA), pure evolutionary, and oracle modes.

---

## 2. Architecture & File Map

### Complete File Tree

```
bagnet_ngspice/
├── bb_envs/src/ngspice/
│   ├── envs/
│   │   └── comp_classab_opamp.yaml          ← Environment config (design space + specs)
│   ├── templates/comp_classab/
│   │   ├── comp_classab_ol.cir              ← Open-loop AC testbench
│   │   ├── comp_classab_cm.cir              ← Common-mode testbench
│   │   ├── comp_classab_ps.cir              ← Power supply rejection testbench
│   │   └── comp_classab_tran.cir            ← Transient testbench
│   ├── wrappers/
│   │   └── comp_classab.py                  ← 4 parser classes
│   └── flows/
│       └── comp_classab.py                  ← Flow coordinator
│
└── specs/iccad/
    ├── comp_classab_bagnet_custom_ea_dropout_multi_sampling.yaml  ← BagNet experiment
    ├── comp_classab_evo_custom_ea.yaml                           ← Pure EA experiment
    └── comp_classab_oracle_custom_ea.yaml                        ← Oracle baseline
```

### How They Connect (Data Flow)

```
specs/iccad/comp_classab_bagnet_*.yaml     (master config)
  │
  ├─→ bb_envs/src/ngspice/envs/comp_classab_opamp.yaml     (what to optimize)
  │     │
  │     ├─→ params: mp_in, mn_in, mp_tail, ...              (design variables)
  │     ├─→ spec_range: gain, ugbw, pm, ...                 (targets)
  │     └─→ ngspice_config:                                 (simulation setup)
  │           │
  │           ├─→ templates/comp_classab/comp_classab_ol.cir
  │           │     └─→ wrappers/comp_classab.py::CompClassABOpenLoop
  │           ├─→ templates/comp_classab/comp_classab_cm.cir
  │           │     └─→ wrappers/comp_classab.py::CompClassABCommonModeGain
  │           ├─→ templates/comp_classab/comp_classab_ps.cir
  │           │     └─→ wrappers/comp_classab.py::CompClassABPowerSupplyGain
  │           └─→ templates/comp_classab/comp_classab_tran.cir
  │                 └─→ wrappers/comp_classab.py::CompClassABTransient
  │
  └─→ flows/comp_classab.py::CompClassABFlow   (orchestrates all 4 testbenches)
```

---

## 3. Circuit Design & 45nm Adaptation

### Original Circuit (180nm)

The user provided a complementary class-AB op-amp with:
- **Complementary NMOS + PMOS differential input pairs** (M1-M4) — extends input common-mode range
- **Folded cascode architecture** with PMOS cascode loads (M7-M10) and NMOS cascode loads (M11-M14)
- **Floating current sources** (M15-M18) — implement class-AB quiescent current control
- **Push-pull class-AB output stage** (M19-M20) — high slew rate, rail-to-rail output
- **Dual compensation capacitors** (Cc1, Cc2) — Miller compensation on both output paths

### What Changed for 45nm

| Aspect | Original (180nm) | Adapted (45nm) | Reason |
|--------|-------------------|-----------------|--------|
| **VDD** | 1.8V | 1.2V | 45nm max reliable supply |
| **Channel Length** | 180nm | 90nm | 2× minimum feature — standard analog practice for gain/matching |
| **Unit Finger Width** | 1µm | 0.5µm | Matches existing two_stage convention; multiplier `m` scales effective width |
| **Vcm** | 0.9V | 0.6V | VDD/2 for balanced operation |
| **Bias Scheme** | 6 independent `vbias` DC sources | Self-biasing current mirrors (20µA reference) | Voltage sources do not scale across technology; current mirrors are process-portable and parameterizable |
| **Model File** | `180nm_bulk.txt` | `45nm_bulk.txt` | BPTM 45nm BSIM4 models (Vth ≈ ±0.22V) |
| **Load** | 10pF \|\| 1kΩ | 10pF only | Consistent with two_stage experiment; resistive load optional |

### Bias Network Design

The original netlist used 6 hardcoded voltage sources (`vbias1` through `vbias6`). These were replaced with a proper self-biasing mirror network:

```
Ibias1 (20µA) → Mnbias (diode-connected NMOS) → generates nbias voltage
Imbias2 (20µA) → Mpbias1 (diode-connected PMOS) → generates pbias voltage

nbias → Mncas_bias (NMOS with Ibias) → generates ncas_bias (NMOS cascode bias)
pbias → Mpcas_bias (PMOS with Ibias) → generates pcas_bias (PMOS cascode bias)
```

This biasing approach:
- Derives all 4 needed bias voltages from a single 20µA reference current
- Makes the bias voltages track process/temperature variations automatically
- The multipliers of the bias transistors are shared with the corresponding circuit transistors (e.g., `mn_tail` is used for both the tail current source and the bias mirror), so the optimizer inherently maintains proper current ratios

### 13 Optimizable Parameters

| Parameter | Component | Range | Step | Description |
|-----------|-----------|-------|------|-------------|
| `mp_in` | M3, M4 | 1–100 | 1 | PMOS differential input pair multiplier |
| `mn_in` | M1, M2 | 1–100 | 1 | NMOS differential input pair multiplier |
| `mp_tail` | M6, Mpbias1 | 1–100 | 1 | PMOS tail current source multiplier |
| `mn_tail` | M5, Mnbias | 1–100 | 1 | NMOS tail current source multiplier |
| `mp_cas` | M9, M10, Mpcas_bias | 1–100 | 1 | PMOS cascode transistor multiplier |
| `mn_cas` | M11, M12, Mncas_bias | 1–100 | 1 | NMOS cascode transistor multiplier |
| `mp_flt` | M16, M18 | 1–100 | 1 | PMOS floating current source multiplier |
| `mn_flt` | M15, M17 | 1–100 | 1 | NMOS floating current source multiplier |
| `mp_load` | M7, M8 | 1–100 | 1 | PMOS load transistor multiplier |
| `mn_load` | M13, M14 | 1–100 | 1 | NMOS load transistor multiplier |
| `mp_out` | M19 | 1–100 | 1 | PMOS output stage multiplier |
| `mn_out` | M20 | 1–100 | 1 | NMOS output stage multiplier |
| `cc` | Cc1, Cc2 | 0.1pF–10pF | 0.1pF | Compensation capacitor value |

Each transistor multiplier of value `m` means `m` parallel fingers of `W=0.5µm, L=90nm`. So `mp_in=20` gives the PMOS input pair an effective width of 10µm.

### 8 Specification Targets

| Spec | Constraint | Unit | Direction |
|------|-----------|------|-----------|
| `gain` | ≥ 300 | V/V | Higher is better |
| `ugbw` | ≥ 10 MHz | Hz | Higher is better |
| `pm` | ≥ 60° | degrees | Higher is better |
| `tset` | ≤ 90 ns | seconds | Lower is better |
| `psrr` | ≥ 50 dB | dB | Higher is better |
| `cmrr` | ≥ 50 dB | dB | Higher is better |
| `offset_sys` | ≤ 1 mV | Volts | Lower is better |
| `ibias` | ≤ 0.5 mA | Amps | Lower is better |

> **Note:** `ibias` limit is set to 0.5mA (vs 0.2mA for two_stage) because the class-AB topology uses more bias branches.

### 4 Testbenches

| Testbench | Simulation | Output Node | What It Measures |
|-----------|-----------|-------------|------------------|
| `comp_classab_ol.cir` | `.ac dec 10 1 10G` | `v(out)` + `i(vdd)` | DC gain, UGBW, Phase margin, Bias current |
| `comp_classab_cm.cir` | `.ac dec 10 1 10G` | `v(out)` | Common-mode gain → CMRR = 20·log₁₀(Adm/Acm) |
| `comp_classab_ps.cir` | `.ac dec 10 1 10G` | `v(out)` | Power supply gain → PSRR = 20·log₁₀(Adm/Aps) |
| `comp_classab_tran.cir` | `.tran 100p 1u` | `v(out)`, `v(net1)`, `i(vdd)` | Settling time (1% band), Systematic offset |

---

## 4. How to Run

### Prerequisites

Make sure the conda environment is active and the `NGSPICE_TMP_DIR` environment variable is set (handled by `run.sh` which sources `.env`):

```bash
conda activate bagnet
```

### Running the Experiment

Three modes are available, matching the two_stage experiment structure:

#### BagNet (DNN + Evolutionary Algorithm) — Recommended
```bash
./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_bagnet_custom_ea_dropout_multi_sampling.yaml
```
Uses a Siamese DNN with MC Dropout to filter EA candidates before simulation. Typically converges in 50 iterations with ~100 simulations.

#### Pure Evolutionary Algorithm
```bash
./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_evo_custom_ea.yaml
```
Uses only crossover + mutation without DNN filtering. Needs more simulations (~1000 steps) but avoids DNN training overhead.

#### Oracle Baseline
```bash
./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_oracle_custom_ea.yaml
```
Uses ground-truth simulation for all candidates (no DNN at all). Slow but provides a verification baseline.

### What Happens During a Run

```
1. INITIALIZE  →  Generate 100 random designs, simulate all 4 testbenches for each
                   (100 × 4 = 400 ngspice runs)

2. TRAIN DNN   →  Build pairwise comparison dataset, train Siamese network

3. OPTIMIZE    →  Loop for up to 50 iterations:
   a. DecisionBox identifies the "bottleneck" spec (e.g., PM is too low)
   b. EA generates ~20,000 candidate designs via crossover/mutation
   c. DNN filters them → selects top 5 most promising
   d. NGSpice simulates the top 5 (5 × 4 = 20 ngspice runs)
   e. Results added to database; netlists saved to good/ or bad/
   f. DNN retrained on updated database

4. FINALIZE    →  Log best solution, generate cost plots
```

### Comparing Runs

After running multiple experiments (e.g., BagNet vs Evo):

```bash
./run.sh deep_ckt/efficient_ga/run_scripts/plot.py \
    outputs/log/comp_classab/bagnet_<timestamp> \
    outputs/log/comp_classab/evo_<timestamp> \
    --legend bagnet evo
```

---

## 5. How to Customize

### A. Change Transistor Sizing Ranges

Edit `bb_envs/src/ngspice/envs/comp_classab_opamp.yaml` under `params:`:

```yaml
# Allow larger output stage (up to 200 fingers = 100µm effective width)
mp_out: !!python/tuple [1, 200, 1]
mn_out: !!python/tuple [1, 200, 1]

# Finer compensation cap resolution
cc: !!python/tuple [!!float 0.05e-12, !!float 15.0e-12, !!float 0.05e-12]
```

**Trade-off:** Wider ranges = larger search space = slower convergence, but may find better designs.

### B. Lock a Parameter (Stop Optimizing It)

Set min = max in the YAML:

```yaml
# Fix output stage NMOS at 50 fingers
mn_out: !!python/tuple [50, 50, 1]
```

This keeps `mn_out=50` in every design without modifying the netlist template.

### C. Change Specification Targets

Edit `spec_range:` in the environment YAML. Format: `[lower_bound, upper_bound, weight]`

```yaml
# Demand higher gain
gain: [!!float 1000.0, null, 1]

# Relax phase margin requirement
pm: [!!float 45.0, null, 1]

# Remove settling time constraint entirely
tset: [null, null, 1]

# Make PSRR 3× more important than other specs
psrr: [!!float 50.0, null, 3]
```

### D. Change Fixed Circuit Parameters

Edit the `.cir` templates in `bb_envs/src/ngspice/templates/comp_classab/`. These values are hardcoded and never touched by the optimizer:

| Parameter | Location in template | Default | Example change |
|-----------|---------------------|---------|---------------|
| Bias current | `.param ibias=20u` | 20µA | `.param ibias=50u` |
| Load capacitor | `.param cload=10p` | 10pF | `.param cload=5p` |
| Common-mode voltage | `.param vcm=0.6` | 0.6V | `.param vcm=0.5` |
| Supply voltage | `vdd VDD 0 dc=1.2` | 1.2V | `vdd VDD 0 dc=1.0` |
| Unit finger width | `.param wp_in=0.5u` | 0.5µm | `.param wp_in=1u` |
| Channel length | `.param lp_in=90n` | 90nm | `.param lp_in=180n` |

> **Important:** Any change to the `.cir` templates must be applied to **all 4 testbench files** (`_ol`, `_cm`, `_ps`, `_tran`) to keep the circuit consistent.

### E. Make a Fixed Value Optimizable

Example: make the bias current optimizable.

1. In **all 4** `.cir` templates, replace:
   ```spice
   .param ibias=20u
   ```
   with:
   ```spice
   .param ibias={{ibias_val}}
   ```

2. In `comp_classab_opamp.yaml`, add under `params:`:
   ```yaml
   ibias_val: !!python/tuple [!!float 5.0e-6, !!float 100.0e-6, !!float 5.0e-6]
   ```

### F. Tune the AI/EA Behavior

Edit the experiment spec YAML (e.g., `comp_classab_bagnet_custom_ea_dropout_multi_sampling.yaml`):

```yaml
agent_params:
  n_init_samples: 200    # More initial random samples (better DNN training, slower start)
  max_n_steps: 100       # More optimization iterations
  n_new_samples: 10      # Simulate 10 designs per iteration instead of 5
  max_iter: 50000        # More DNN queries per iteration (better filtering)

  model_params:
    keep_prob: 0.6        # Lower = more exploration (higher uncertainty)
    learning_rate: 0.0005 # Slower, more stable training

ea_params:
  cxpb: 0.7              # 70% crossover probability
  mutpb: 0.3              # 30% mutation probability
```

### G. Change Parallelism

In `comp_classab_opamp.yaml`:

```yaml
num_workers: 8    # Use 8 parallel ngspice processes (default: 4)
```

### H. Change Feedback Factor

For non-unity feedback (e.g., gain-of-2 configuration):

```yaml
feedback_factor: !!float 0.5   # 1/β = 2, so β = 0.5
```

This affects settling time calculation in the transient testbench.

---

## 6. Outputs, Storage & Interpretation

### Output Directory Structure

Each run creates a timestamped directory:

```
outputs/log/comp_classab/
└── bagnet_DD-MM-YYYY_HH-MM-SS/
    ├── progress_log.txt         ← Full text log of the run
    ├── db.pkl                   ← Pickled database of all designs
    ├── db_time.pkl              ← Database with timing statistics
    ├── avg_prediction.txt       ← Per-query DNN probability predictions
    ├── checkpoint/              ← Saved DNN model weights
    │   ├── checkpoint
    │   ├── checkpoint.ckpt.data-00000-of-00001
    │   ├── checkpoint.ckpt.index
    │   └── checkpoint.ckpt.meta
    ├── cost_vs_iter.png         ← Auto-generated plot (cost over iterations)
    └── cost_vs_nquery.png       ← Auto-generated plot (cost over NN queries)
```

### Netlist Segregation

During optimization, every simulated design's netlists are saved:

```
outputs/netlists/
├── good/    ← Designs that beat the current best cost at time of evaluation
│   ├── <ID>_comp_classab_ol.cir
│   ├── <ID>_comp_classab_cm.cir
│   ├── <ID>_comp_classab_ps.cir
│   └── <ID>_comp_classab_tran.cir
│
└── bad/     ← All other valid designs (did not improve best cost)
    └── ...
```

### Understanding the Outputs

#### `progress_log.txt`

The most important output file. Contains:

```
--- Iteration 0 ---
Training DNN ...
  gain accuracy: 0.85, loss: 0.42
  ugbw accuracy: 0.78, loss: 0.55
  pm   accuracy: 0.82, loss: 0.48
  ...
best_cost = 0.234
best_spec = {'gain': 456.2, 'ugbw': 12.3e6, 'pm': 62.1, ...}
best_design = [23, 45, 12, 8, ...]
```

**Key fields:**
| Field | Meaning |
|-------|---------|
| `best_cost` | Sum of normalized constraint violations. **0.0 = all specs met.** Lower is better. |
| `best_spec` | Dictionary of actual performance metrics for the best design so far |
| `best_design` | Parameter vector (integer indices into the discretized parameter grid) |
| Accuracy per spec | How well the DNN predicts pairwise comparisons (closer to 1.0 = better) |

#### `cost` — How It Works

The cost function penalizes only **violated** constraints:

```
cost = Σ max(0, (target - actual) / target)    for "≥" constraints (gain, ugbw, pm, psrr, cmrr)
     + Σ max(0, (actual - target) / target)    for "≤" constraints (tset, offset_sys, ibias)
```

- **cost = 0** → All 8 specs are satisfied simultaneously
- **cost > 0** → One or more specs are violated; the value indicates how far off

#### `cost_vs_iter.png`

Shows how the best cost decreases over optimization iterations. A good run shows:
- Rapid decrease in the first ~10 iterations (DNN learns quickly)
- Gradual convergence toward 0 (or a plateau if specs are very aggressive)

#### `cost_vs_nquery.png`

Shows cost reduction vs. total number of DNN queries. Useful for comparing:
- **BagNet** (few simulations, many DNN queries) vs. **Evo** (many simulations, no DNN queries)
- The BagNet curve should be far to the left of the Evo curve for the same cost value

#### `db.pkl` and `db_time.pkl`

Pickled Python objects containing the full history:

```python
import pickle

# Load the database
with open('outputs/log/comp_classab/bagnet_<timestamp>/db.pkl', 'rb') as f:
    db = pickle.load(f)

# db is a list of lists: db[iteration] = [Design, Design, ...]
# Each Design has: .specs (dict), .value_dict (parameter values), .id (unique string)

# Load timing info
with open('outputs/log/comp_classab/bagnet_<timestamp>/db_time.pkl', 'rb') as f:
    data = pickle.load(f)
# data contains: 'db', 'n_nn_query', 'nn_query_time', 'n_sims', 'sims_time',
#                'n_training', 'training_time', 'total_time'
```

### Extracting the Best Circuit

Use the provided utility script:

```bash
python parse_best_circuit.py outputs/log/comp_classab/bagnet_<timestamp>/progress_log.txt
```

This prints:
- **Best cost** — the lowest cost achieved
- **Best specifications** — gain, UGBW, PM, etc. of the winning design
- **Best parameter vector** — the integer multipliers that produce the winning design

### Re-Simulating Saved Netlists

To independently verify the good designs:

```bash
python run_good_netlists.py
```

This:
1. Finds all unique design IDs in `outputs/netlists/good/`
2. Rewrites netlist paths for local simulation
3. Runs ngspice on all 4 testbenches per design
4. Writes results to `good_netlists_metrics.csv`

The CSV uses status indicators:
- **✅ Pass** — meets the constraint
- **⚠️ Near** — within 10% of the constraint boundary
- **❌ Fail** — violates the constraint

### Mapping Parameter Vector Back to Physical Values

The optimizer works with integer indices. To convert back to physical values:

```python
# From the YAML params: [min, max, step]
# Physical value = min + index × step

# Example: mp_in index = 23
# mp_in range: [1, 100, 1]
# Physical value = 1 + 23 × 1 = 24 fingers
# Effective width = 24 × 0.5µm = 12µm at L = 90nm

# Example: cc index = 45
# cc range: [0.1e-12, 10e-12, 0.1e-12]
# Physical value = 0.1e-12 + 45 × 0.1e-12 = 4.6 pF
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Run BagNet optimization | `./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_bagnet_custom_ea_dropout_multi_sampling.yaml` |
| Run pure EA optimization | `./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_evo_custom_ea.yaml` |
| Run oracle baseline | `./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/iccad/comp_classab_oracle_custom_ea.yaml` |
| Extract best circuit | `python parse_best_circuit.py outputs/log/comp_classab/bagnet_<timestamp>/progress_log.txt` |
| Re-simulate good designs | `python run_good_netlists.py` |
| Compare runs | `./run.sh deep_ckt/efficient_ga/run_scripts/plot.py <logdir1> <logdir2> --legend bagnet evo` |
