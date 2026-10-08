# Executor and inference experiment

This experiment compares decision-to-action behavior in two configurations:
**native GaP + Astra** and **GaP + Jev + a custom Rust executor**. It uses
matched simulated observations and a shared controller to measure the combined
effect of executor and model choice on task completion and latency.

The same policy graph produces action proposals for a shared controller. This
repository includes a Rust executor, Python workers, MuJoCo YAM demonstrations,
timing logs and reproducible result summaries.

| System | Graph | Executor | Decision model |
|---|---|---|---|
| **A** | GaP workflow | Native GaP | OpenAI GPT-6 Astra |
| **B** | Same GaP workflow | Custom Rust executor | TypeSafe Jev |

![Moving-cube comparison](assets/moving-cube.png)

**[Watch the side-by-side demo](assets/moving-cube.mp4)** ·
[Results and limitations](results.md) · [Architecture](architecture.md) ·
[YAM hardware guide](hardware.md)

## Execution paths

**GaP supplies the workflow format and the native executor used by A.** We build
on [graph-robots/graph-as-policy](https://github.com/graph-robots/graph-as-policy),
pinned by `gap-commit.txt`. Our selected graph has three steps: prepare the
observation, request a decision, and produce an action proposal.

These are custom benchmark workers registered through GaP's `ToolRegistry`.
This experiment does not use GaP's existing robot skill catalog. The shared
YAM tracking and grasp controller is also custom.

```mermaid
flowchart LR
    S[Observation] --> G[Same GaP workflow]
    G --> A[A: Native GaP executor]
    G --> I[B: Supported-subset importer]
    I --> R[Custom Rust executor]
    A --> M[Astra decision worker]
    R --> J[Jev decision worker]
    M --> P[Action proposal]
    J --> P
    P --> Q[Common admission gate]
    Q --> C[Same tracking controller]
    C --> Y[YAM simulation]
    Y --> S
```

In **A**, upstream GaP executes the graph and calls Astra through our Python
decision worker. Its scheduler and normal tracing are preserved.

In **B**, our importer reads the same graph into a limited Rust representation.
The Rust executor starts a node when its required control and data inputs are
ready. It calls persistent Python workers over Unix-domain sockets and collects
their results. The decision worker calls **Jev**, which chooses one of
`continue`, `reperceive`, `replan` or `abort`. B uses GaP's graph specification;
it does not run the native GaP executor inside Rust.

Both paths return an `ActionProposal` carrying the observation identity and
timestamp. The shared gate checks it before the controller acts. Neither model
receives an actuator handle or writes motor commands.

For the moving-cube demo, the model authorizes pickup once. The same controller
then tracks the cube using live simulator state, closes the fingers, lifts and
holds it. The model is not the low-level motion controller. The joint-target
pilot instead requests repeated decisions as observations arrive.

The purpose is to measure the complete decision-to-action path. Since B changes
both execution and the decision model, an A/B timing difference cannot tell us
how much came from Jev versus the Rust executor.

## Moving-cube result

One matched moving-cube episode per system:

| System | Confirmed pickup | Retained at episode end |
|---|---:|---|
| A — Native GaP + Astra | 8.79 s | Yes |
| B — GaP + Jev + custom Rust executor | 5.42 s | Yes |

Pickup means the cube center is more than 5 cm above the table with opposing
finger contact sustained for 300 ms. Both episodes ran for 18 seconds with the
same initial state, model and controller. The video uses synchronized 1× wall-time
playback and shows the confirmed pickup time.

**This is an integration demo, not a statistical speedup claim.** The task uses
simulator ground truth and experimental fingertip contact pads. A deterministic
rule could authorize the same pickup. The comparison changes execution **and**
inference, so it does not isolate the Rust executor's contribution. No physical
hardware result or semantic-quality equivalence is claimed.

## Installation

Use Ubuntu 24.04 or WSL2 for development. Use native Linux for published timing
studies. Keep the checkout, environment and outputs on Linux storage when possible.
Install Git, [uv](https://docs.astral.sh/uv/getting-started/installation/),
[Rust](https://rustup.rs/) and system OpenGL libraries first:

```bash
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libegl1 libgl1 libglfw3
# From this repository's root:
bash scripts/setup.sh
bash scripts/check.sh
```

Setup fetches pinned GaP and I2RT checkouts into ignored `vendor/`, creates the
Python 3.12.3 environment under `$HOME/.local/share/rtbench/yam-venv`, and builds
Rust 1.98.1 under `$HOME/.cache/rtbench/target`. Dependency versions are committed.
`RTBENCH_ENV` and `CARGO_TARGET_DIR` override these locations. When overriding the
build directory, set `RTBENCH_BINARY` to its `release/rtbench-runtime` binary.

### Run locally without model APIs

```bash
PY="$HOME/.local/share/rtbench/yam-venv/bin/python"
"$PY" scripts/moving_cube.py --diagnostic --duration 18 \
  --output "$HOME/.local/share/rtbench/results/cube-check"
"$PY" scripts/cube_video.py "$HOME/.local/share/rtbench/results/cube-check" --diagnostic
```

This verifies contact-based pickup with a deterministic decision. It is **not**
an A/B model comparison. The diagnostic runs unpaced; its timeline is simulation
time. Choose a new output directory for every run.

### Run one live A/B pair

Agents must ask the user before spending OpenAI API credits. The `--live` flag
enables execution and does not replace that approval.

Create credential files outside the checkout, then provide their paths:

```bash
export ASTRA_KEY_FILE="/path/to/private/astra.key"
export JEV_KEY_FILE="/path/to/private/jev.key"
PY="$HOME/.local/share/rtbench/yam-venv/bin/python"
"$PY" scripts/moving_cube.py --live --duration 18 \
  --output "$HOME/.local/share/rtbench/results/cube-pair"
"$PY" scripts/cube_video.py "$HOME/.local/share/rtbench/results/cube-pair"
```

Live mode makes billable requests and sends synthetic task state to OpenAI and
TypeSafe. It does not transmit images or hardware data. Model IDs are
`gpt-6-astra` (low reasoning effort) and pinned `jev-1.13.0`. Local, shared spending
guards default to **$100 for Astra / $5 for Jev**; see [configuration](configuration.md).

### Run the joint-target pilot

```bash
"$PY" scripts/yam_sim.py --live --pairs 5 --duration 12 \
  --output "$HOME/.local/share/rtbench/results/joint-pairs"
"$PY" scripts/yam_report.py "$HOME/.local/share/rtbench/results/joint-pairs"
```

Five pairs are ten episodes: one static pair, two early-change pairs and two
late-change pairs. `--diagnostic` substitutes local decisions for plumbing tests.

## Hardware requirements

These runners use simulated YAM control. Physical dispatch requires a calibrated
controller bridge, validated perception and command-completion checks. See the
[hardware guide](hardware.md) and [station interfaces](station.md).

For repeated model decisions, see the [continuous-decision experiment](continuous.md).
For GaP, CaP-X, ASPIRE and ENPIRE across the shared 13-task inventory, see the
[harness guide](../task_suite/HARNESSES.md) and [testing plan](../task_suite/TESTING_PLAN.md).
