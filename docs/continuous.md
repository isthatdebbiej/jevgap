# Continuous observation and decision benchmark

The original moving-cube demo requests one pickup authorization. The continuous
runner requests decisions throughout the episode while physics and observations
continue independently of inference. It reuses the same GaP graph in A and B.

One request runs at a time. A single pending observation is replaced by the newest
sample; replacement counts are recorded. A scripted cube-motion reversal creates
a new scene version and invalidates the current authorization. Responses from
older scenes cannot renew it. Admission and scene updates use the same lock.
The controller checks scene version, observation age and authorization expiry on
every tick. Pausing commands holds the current joint target; it does not instantly
stop an already moving physical arm. This controller is simulation-only.

## Run offline first

After `bash scripts/setup.sh`, use the Python environment created by setup:

```bash
PY="$HOME/.local/share/rtbench/yam-venv/bin/python"
OUT="$HOME/.local/share/rtbench/results/continuous-groundtruth"
"$PY" scripts/continuous.py --diagnostic --pairs 3 --worker-delay-s .4 --output "$OUT"
"$PY" scripts/continuous_report.py "$OUT"
"$PY" scripts/cube_video.py "$OUT/pair-0"
```

Both diagnostic paths use the same deterministic decision and requested sleep.
They make no model calls and must not be presented as Astra/Jev results. The sleep
models external waiting, not CPU compute. Actual worker durations are recorded.
Collection order is randomized, scene parameters are matched, and all episodes
are retained. Repetitions use the same scene rather than a diverse task set.

## Camera-derived state

```bash
"$PY" scripts/continuous.py --diagnostic --perception camera --pairs 1 \
  --worker-delay-s .4 --output "$HOME/.local/share/rtbench/results/continuous-camera"
```

This mode renders a calibrated, fixed elevated RGB-D camera. A color detector
finds the known red cube and projects depth into robot/world coordinates. It uses
the known cube dimensions and upright orientation to estimate its center. It
does not read ground-truth object position or velocity for decision input or
tracking targets. Ground truth is retained for perception-error and success
scoring; simulator contact measurements are still used by the grasp controller.
Missing detections pause tracking. Confidence is a pixel-count heuristic, not a
calibrated probability. Depth noise, lighting variation and arbitrary objects are
not modeled. No GaP perception bundle is integrated yet.

The scene-change trigger remains a simulator event in both perception modes.
A camera-derived motion-change detector is a separate remaining task. Rendering runs on a separate thread using copied joint state. The physics loop
continues during rendering and inference. Camera snapshots older than 750 ms or
from a previous scene are excluded. Shared CPU contention can still lower the
achieved real-time factor; this is recorded. The visible-surface centroid is an
approximate cube-center estimate, and its error is measured against ground truth.

## Live A/B

Set `ASTRA_KEY_FILE` and `JEV_KEY_FILE` as described in configuration.md. Existing
durable provider budget caps apply. Limit each development episode explicitly:

```bash
"$PY" scripts/continuous.py --live --pairs 1 --max-calls 6 --duration 12 \
  --output "$HOME/.local/share/rtbench/results/continuous-live"
```

A uses native GaP + Astra; B uses the same GaP graph + Jev + the custom Rust
executor. A workflow failure ends further inference in that episode, while
physics continues. Timeouts retain budget reservations; there are no retries.
Calls still running when physics ends are recorded on completion and their
proposals are rejected. Per-episode call limits can expire before the episode
ends; summaries record that condition. Diagnostic settings do not alter live
provider delays.

## Measurements and interpretation

Each run writes config/source hashes, per-episode JSONL records and summaries.
Logs include observation capture, perception completion, request submission,
worker start/end, decision completion, gate checks and controller dispatch.
Rust also supplies node dispatch and result-receipt timestamps. Native GaP's
wrapper provides output-ready eligibility estimates for uniquely named tool
invocations, not internal queue timestamps. Normal native tracing is preserved.

Report full workflow latency and change-to-fresh-dispatch separately. Also retain
pickup success, stale/expired proposals, pending replacements, paused ticks,
missing observations, perception error, worker failures and real-time factor.
An admitted decision is not proof of semantic correctness or pickup success.
The small development report is descriptive; it does not assert statistical
significance or hard real-time behavior.

The present decision rule is simple enough to implement deterministically. These
trials test integration and reaction latency, not the necessity of an LLM. Before
claiming equivalent semantic quality, select an actual semantic task, freeze
independently labeled episode-grouped states and compare both models on that
same dataset. No semantic non-inferiority result is claimed here.

Next hardware dependencies are camera/arm calibration, an image-based scene
detector, a validated perception pipeline and a hardware controller/watchdog.
The simulation control gains and grasp contacts must not be copied to hardware.

## Freeze and evaluate semantic states

The model evaluation runner is independent of the simulator. Supply JSONL records
with exactly these fields (labels and provenance must come from the evaluation
design, not from the model being evaluated):

```json
{"id":"example-1","episode_id":"episode-1","state":{"observation":"target occluded"},"gold_decision":"reperceive","provenance":"independent human label; source episode identifier"}
```

```bash
"$PY" scripts/decision_eval.py freeze labeled-states.jsonl frozen-dataset
"$PY" scripts/decision_eval.py run frozen-dataset evaluation-output --live
```

Freezing stores the dataset hash, episode count, prompts, model names and adapter
source hashes. Evaluation refuses modified inputs/contracts, randomizes case and
provider order, records every response/error and scores paired correctness.
Invalid responses count against accuracy. The output includes confusion matrices,
latency, completed-call cost estimates and episode IDs for subsequent clustered
analysis. Uncertain failed calls can still incur charges reserved in the provider
ledgers. This runner does not grant the 2-percentage-point quality gate: a separate
200-example pilot, sample-size design and frozen final evaluation remain required.
No labeled semantic evaluation dataset or quality result is fabricated here.

Development measurements, including unsuccessful camera trials, are in [the results directory](results/continuous/README.md).
