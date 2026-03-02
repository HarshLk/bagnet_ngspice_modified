# BagNet: Custom Topology & Optimization Guide

This guide provides a comprehensive walkthrough for implementing and optimizing a custom circuit topology (e.g., Folded Cascode, Bandgap Reference, LDO) using the **BagNet** framework.

---

## 1. System Overview
BagNet optimizes analog circuits by combining **Evolutionary Algorithms (EA)** with a **Siamese Deep Neural Network (DNN)**. To add a new topology, you must define the circuit's hardware (Netlist), its constraints (Environment YAML), and its measurement logic (Python Wrappers).

### The "Big Four" Files
Every topology requires four interconnected files:
1.  **Netlist Template (`.cir`)**: The SPICE description with Jinja2 placeholders.
2.  **Environment Config (`envs/*.yaml`)**: Defines the search space and performance targets.
3.  **Logic Layer (`wrappers/*.py` & `flows/*.py`)**: Instructions for parsing simulation results.
4.  **Experiment Spec (`specs/*.yaml`)**: The master configuration for the AI and EA.

---

## 2. Step 1: Designing the Netlist Template
BagNet uses standard **NGSpice** netlists. However, instead of hardcoded values for components you want to optimize, you use **Jinja2 placeholders** (`{{ }}`).

*   **Location:** `bb_envs/src/ngspice/templates/<your_topology>/`
*   **Rule:** Any value inside `{{ }}` is a potential target for the optimizer.

### Example: `folded_cascode.cir`
```spice
* Folded Cascode Op-Amp Template
.include "models/45nm_bulk.txt"

* The optimizer WILL explore these:
M1 out_p inn tail vss nmos W={{ w_in }} L=45n
M2 out_n inp tail vss nmos W={{ w_in }} L=45n
C_load out_p vss {{ cload }}

* The optimizer WILL NOT touch these (Hardcoded):
R_bias vdd bias_node 10k
V_supply vdd 0 1.1
```

---

## 3. Step 2: Configuring the Environment YAML
The Environment YAML is the "Rules of the Game." It defines what the optimizer is allowed to change and what metrics it must satisfy.

*   **Location:** `bb_envs/src/ngspice/envs/<your_topology>.yaml`

### Detailed Section Breakdown:

#### A. `params` (The Design Space)
Defines the boundaries for the parameters used in your `.cir` template.
*   **Format:** `name: [min, max, step]`
```yaml
params:
  w_in: [1e-6, 50e-6, 0.5e-6]  # Search width from 1u to 50u
  cload: [0.1e-12, 10e-12, 0.1e-12] # Search cap from 100f to 10p
```

#### B. `spec_range` (The Goals)
Defines the performance targets you want the circuit to meet.
*   **Format:** `name: [min_target, max_target, weight]`
*   Use `null` to indicate no boundary in that direction.
```yaml
spec_range:
  gain: [500.0, null, 1]  # Target: Gain > 500
  ibias: [null, 1.0e-3, 1] # Target: Bias Current < 1mA
```

#### C. `ngspice_config`
Links your specific simulation types (AC, DC, Tran) to their respective templates and Python wrappers.

---

## 4. Step 3: The Logic Layer (Wrappers & Flows)
BagNet needs a "translator" to turn raw SPICE text files into structured data.

### The Wrapper (`wrappers/*.py`)
A Python class that:
1.  **Parses** the `.csv` or `.hdf5` output files from NGSpice.
2.  **Calculates** metrics (e.g., converts Vout/Vin to dB Gain).

### The Flow (`flows/*.py`)
A coordinator that ensures all required simulations (e.g., Open Loop + Transient) are run for a single design candidate before the final performance is calculated.

---

## 5. Step 4: The Experiment Spec (`specs/*.yaml`)
This is the file you provide to the execution command. It configures the "AI behavior."

*   **`n_init_samples`**: Number of random simulations to run initially to "teach" the Neural Network.
*   **`model_params`**: Configures the Siamese DNN depth and `keep_prob` (uncertainty).
*   **`ea_params`**: Configures Crossover (`cxpb`) and Mutation (`mutpb`) probabilities.

---

## 6. How Constraints Work
A critical concept in BagNet is how it restricts the optimizer.

### Can You Constrain What the Optimizer Changes?
**Yes.** The optimizer is strictly limited by a "Double Lock" system. It only touches a value if:
1.  It is listed as a `{{placeholder}}` in the `.cir` template.
2.  **AND** it is listed under the `params:` section in the Environment YAML.

### How to "Fix" a Parameter
If you want to temporarily stop the optimizer from changing a value without editing your netlist:
*   Set the `min` and `max` in the YAML to the same value:
    ```yaml
    params:
      w_in: [10e-6, 10e-6, 1] # Now fixed at 10u
    ```

---

## 7. Execution
To start the optimization for your custom topology:

1.  Ensure your four files are configured.
2.  Run the main script using the experiment spec:

```bash
./run.sh deep_ckt/efficient_ga/run_scripts/main.py specs/<your_experiment>.yaml
```

### The Optimization Cycle:
1.  **Initialize:** Run random SPICE simulations.
2.  **Learn:** Train Siamese DNN on results.
3.  **Identify:** DecisionBox finds the "Bottleneck" metric (e.g., PM is too low).
4.  **Filter:** EA generates 20k designs; DNN filters them down to the top 5.
5.  **Validate:** NGSpice simulates the top 5.
6.  **Update:** New results are added to the DB, and the DNN is re-trained.
