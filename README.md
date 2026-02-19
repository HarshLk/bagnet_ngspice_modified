## BagNet release for NGSPICE
This repo contains the demo code for demonstraing the algorithm of BagNet in ngspice environment.
BagNet results have been demonstrated in [ICCAD 2019](https://ieeexplore.ieee.org/document/8942062) and [DAC 2019](https://ieeexplore.ieee.org/document/8807032).

BagNet demo on BAG (Berkeley Analag Generator) with post layout simulations is comming soon.

# setup

Clone the repo and update the submodules.

```
git clone
cd repo
git submodule update --init --recursive
```

# NGSpice installation
NGspice 2.7 needs to be installed separately, via this [installation link](https://sourceforge.net/projects/ngspice/files/ng-spice-rework/old-releases/27/). Page 607 of the pdf manual on the website has instructions on how to install. Note that you might need to remove some of the flags to get it to install correctly for your machine.

# Code structure
This repo contains two submodule:

* ([bb_envs](https://github.com/kouroshHakha/bb_envs.git)):
Contains example implementations of black-box environments used for optimization. For more info go to the link and read the documentation.
* ([deep_ckt](https://github.com/kouroshHakha/bag_deep_ckt/tree/bagnet_ngspice_release)):
Contains the submodules for black-box env framework and the algorithms used for circuit optimization. Look into the submodule for more details.

# running prepared experiements

`command.sh` contains the commands that reproduce the results of ICCAD paper for the two stage opamp optimization problem. You can comment/un-comment the sections that you deem necessary.

```
./commands.sh
```

# running custom experiments
For custom experiments, a yaml file containing algorithm specifications should be passed to top level script located at `./deep_ckt/efficient_ga/run_scripts/main.py`.
For example:

```
./run.sh ./deep_ckt/efficient_ga/run_scripts/main.py specs/examples/cs_amp.yaml
```

---

# Detailed Architecture & Workflow

BagNet is a high-efficiency analog design optimizer that uses a **Siamese Deep Neural Network (DNN)** as a surrogate filter to accelerate evolutionary search.

### 1. Core Architecture
- **BagNet Agent (`BagNetAgent`):** The central orchestrator that manages the optimization loop, integrating the machine learning model with the evolutionary search.
- **Siamese DNN (`DropOutModel`):** A neural network (TensorFlow 1.x) that performs pairwise comparisons between designs. It predicts which design is "better" for specific specifications rather than predicting absolute performance. It uses **Monte Carlo Dropout** for Bayesian uncertainty estimation.
- **Decision Box (`DecisionBox`):** A heuristic engine that identifies "critical specifications" (those contributing most to the cost function) and selects "reference designs" to guide the search.
- **Custom EA (`CustomEA`):** An evolutionary algorithm (built on `deap`) that generates new candidate designs using crossover and mutation operators tailored for circuit parameters.
- **NGSpice Integration (`bb_envs`):** A black-box evaluation engine that interfaces with NGSpice 2.7 for ground-truth simulations.

### 2. Automated Netlist Generation
Netlists are generated through a multi-layered process:
- **YAML Configuration:** Parameters (widths, multipliers, capacitors) and their ranges are defined in `bb_envs/src/ngspice/envs/two_stage_opamp.yaml`.
- **Jinja2 Templating:** Base circuit files in `bb_envs/src/ngspice/templates/two_stage_full/` (e.g., `two_stage_ol.cir`) contain placeholders like `{{ mp1 }}` or `{{ cc }}`.
- **Rendering:** Python injects the optimized parameters into these templates to create unique `.cir` files for every simulation run.
- **Multi-Bench Simulation:** For every design, the system typically runs 4 testbenches:
    - **Open Loop (`ol`)**: Differential gain, UGBW, Phase Margin, Bias Current.
    - **Common Mode (`cm`)**: Common-mode gain for CMRR calculation.
    - **Power Supply (`ps`)**: Power supply gain for PSRR calculation.
    - **Transient (`tran`)**: Settling time and systematic offset.

### 3. Customization & Experiments
To customize the optimization or run new experiments:
- **To Change Constraints:** Update the `spec_range` in the environment YAML (e.g., `two_stage_opamp.yaml`).
- **To Fix Parameters:** Set the range in the YAML to a single value (e.g., `mn4: [50, 50, 1]`) or hardcode the value directly in the `.cir` template.
- **To Modify Topology:** Edit the SPICE templates in `bb_envs/src/ngspice/templates/`. You can add or remove transistors and add corresponding placeholders for the optimizer to explore.

### 4. Logging & Performance Metrics
- **Log Location:** Standard logs and plots are stored in `outputs/log/two_stage/bagnet/`.
- **Netlist Segregation:** Successfully simulated netlists are automatically segregated:
    - `outputs/netlists/good`: Netlists that improved the current best design performance.
    - `outputs/netlists/bad`: All other successfully simulated netlists.
- **Metrics Summary:** A summary CSV (`good_netlists_metrics.csv`) is generated containing detailed performance tables for all "good" designs, including Gain, UGBW, Phase Margin, Settling Time, PSRR, CMRR, and Offset.
