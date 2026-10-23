# Operator handoff — ACT, Qwen, GaP versus CaP

The software packet is ready for supervised station commissioning. No physical
trial has been run as part of this preparation. Commissioning verifies physical
facts; it is not part of the scored comparison.

## Selected experiment

- Station: `se3-labs-yam-2`, Tailscale `100.107.161.92:7443`.
- Controller: official SE3 ACT Harness. Open model: `Qwen/Qwen3.8-27B`.
- Each episode: at most 450 seconds and 52 model requests, same for both methods.
- User-approved open-model reservation ceiling: $230; $0.50 previously reserved.
  The 44-episode plan can reserve at most $228.80 more, leaving $0.70 for
  additional diagnostic reservations. This is client reservation accounting;
  provider charges must be checked against provider billing. Failed calls retain
  their reservation; the ledger is never reset between runs. Extra commissioning
  calls consume the same ceiling and can reduce the remaining collection budget.
- Astra configuration is preserved.

## Authoritative packet

Use `operator-packet-v3`, not the older v1/v2 packets. It includes 17 base task
profiles: the ten physical proposal tasks, three explicitly supplemental tasks
from the earlier 13-task list, and four precision/memory variants. Six balanced
language assignments replace the single language task in the collection plan:
22 matched pairs / 44 individual episodes, with policy order alternating.
This is a plan, not an automatic robot batch. Select the intended pair and reset
between methods. The maximum rollout time alone is 5.5 hours for the whole plan;
setup, scoring and resets take additional time.

`protocol.json` fixes measurement thresholds and the plan hash. `plan.json`
records each exact task hash. `tasks/` contains snapshots. `scores/` contains
operator questions and blank evidence forms. Blank answers are deliberately
invalid; they cannot accidentally turn into zero or success scores.

## Reconciliation with the proposal

| Task | Physical definition | Progress milestones |
|---|---|---|
| Pack objects | Car nose, shoe toe, toothbrush head, hammer striking face left; aligned box | 0/10/25/50/100 |
| Hang mugs | Two mugs, separate pegs, upright rack | 0/40/100, adapted |
| Cover blocks | Green, light blue, dark blue; cover left-to-right, reveal by color | 0/5/15/30/100 |
| Press by number | Left x9, right confirm, middle x1, right confirm | 0/100 |
| Plug in charger | One marked outlet; disconnected strip; flush normal fit | 0/100 |
| Insert tubes | Two capped tubes, two marked wells and depth marks | 0/50/100, adapted |
| Classify objects | Writing tools 2; vehicle 1; camera equipment 3; any pure bin assignment | 0/15/40/100 |
| Stacking toy | All 15 pieces, five complete peg groups | 0/10/25/45/70/100, extended |
| Align blocks | Metal ruler; three purple cubes; no lifting | 0/100 |
| Classify by language | Peppers 3, figurines 2, watches 3; all six mappings balanced | 0/10/40/100 |
| Stack bowls | Three bowls, local supplemental task | 0/15/100 |
| Stack blocks | Three blocks, local supplemental task | 0/15/100 |
| Largest number | Four upright tiles 2/4/7/9, target 9742; local supplemental | 0/5/15/30/100 |

Adapted mug/tube/toy quality applies the proposal's 30/30/40 decomposition to the
adapted intervals. These are declared implementation adaptations, not quotations
of the original three-mug, three-tube or four-group rubric. All real-world
profiles are labelled non-comparable to the simulation benchmark. Supplemental
phase rubrics are explicitly local. Their inventories are not claimed to appear
in the ten-task proposal.

For cover-blocks, use a recorded permutation of the three initial color positions,
identical for each matched pair; cycle the six permutations across repetitions.
Do not show the private reset record to either policy after covering.

## Scores and evidence

General Progress is the furthest cumulative milestone reached. Breakdown Quality
is the sum of three phase scores for every adjacent interval: 30%, 30%, 40% of
its width. Success earns full phase points, Partial half, Failure zero. A later
interval is eligible only if its lower milestone was reached. Completed earlier
intervals still receive their actual grades; they are never automatically awarded
full quality. Recovered trajectories may have progress 100 and quality below 100.
Final task success is separate and can be false after a previously reached
milestone is lost. Missing/invalid answers invalidate the export.

SE3 shows every question. Its generic aggregate is intentionally zero because it
cannot express two independent metrics and conditional eligibility. Use
`study-scores.json`, generated from the actual SE3 answers, for the two study
metrics. Never publish the station's generic aggregate as a study score. Unscored
episodes export null metrics, not failure scores. Raw SE3 results are retained.
For manual answer exports:

```bash
PYTHONPATH=task_suite .venv-linux/bin/python -m rtbench_tasks.act_scoring \
  --task operator-packet-v3/tasks/pack-objects-into-box.json \
  --answers completed-answers.json --output scored-result.json
```

Precision/memory retains its own proposal scoring, not invented RoboDojo progress
weights. Record actual choices, measured centre/yaw errors, two-second stability,
release, completion times, retries, drops, early movement and assistance for each
attempted required transfer. Remove unattempted rows from the measurement form;
do not fill them with fabricated zeros. Memory correctness is reported separately
from geometry. Moving-cube evidence records hold/clearance/lock/fresh observation,
stale-command rejection and recovery. The prescribed fixture move is excluded
from assistance; all other assistance is counted. Score with:

```bash
PYTHONPATH=task_suite .venv-linux/bin/python -m rtbench_tasks.act_precision_score \
  --evidence completed-measurements.json --output precision-result.json
```

These evaluators calculate scores from independent observations; they do not
claim to infer calibrated measurements automatically from camera images.

## Commissioning session

Bring the five A/B/C/D/E arrow-labelled cubes, neutral T1/T2/T3 targets and
D1/D2/E1/E2 buffers for the initial memory pair. One A cube is insufficient.
For other tasks, use each task's reset sheet. The moving variant also needs the
indexed locking carrier. Prepare overhead/side measurement video and the reset
photos. The ACT default start joints are `(0, 1.5, 1.5, 0, 0, 0)` per arm;
verify the pose and physical reachable paths at the station. ACT's displacement
limits are not a collision model.

Use `protocol.json` to verify measurement resolution and frozen thresholds.
It distinguishes proposal thresholds from local operational choices. If the
station cannot resolve them, revise and re-freeze before collection, never
between the two methods. Enter the operator, calibration ID, evidence location
and verified checks into `commissioning.json` only after observation.

Validate offline or require the completed station checks:

```bash
PYTHONPATH=task_suite .venv-linux/bin/python -m rtbench_tasks.act_prepare \
  --output operator-packet-v3 --verify
PYTHONPATH=task_suite .venv-linux/bin/python -m rtbench_tasks.act_prepare \
  --output operator-packet-v3 --verify --require-commissioned
```

The second command deliberately fails before commissioning. This is expected.
The service enforces this gate for study profiles. For a supervised commissioning
trial, add `--commissioning-trial`; it is recorded in the manifest and excluded
from the comparison. No command below has been launched against the robot.

## One-episode launch, two Linux/WSL terminals

Start in `/mnt/c/Users/dshek/OneDrive/Documents/ChatGPT/GaP`. Use fresh output,
socket and cue paths per episode. Start the agent when the operator is ready to
start rollout; the agent waits 60 seconds. The service runs only one episode.

```bash
export PYTHONPATH="$PWD/task_suite"
.venv-linux/bin/python -m rtbench_tasks.act_run serve \
  --task operator-packet-v3/tasks/precision-memory-delayed.json \
  --packet operator-packet-v3 --commissioning-trial \
  --socket /tmp/precision-commission-01.sock \
  --output act-runs/precision-commission-01-service \
  --auth-file /mnt/c/Users/dshek/.se3labs/production.json \
  --station se3-labs-yam-2 --address 100.107.161.92:7443 --live
```

```bash
export PYTHONPATH="$PWD/task_suite"
.venv-linux/bin/python -m rtbench_tasks.act_run agent \
  --task operator-packet-v3/tasks/precision-memory-delayed.json \
  --model act-config/qwen.json --harness native-gap \
  --gap-root /mnt/c/Users/dshek/Work/Robotics/rt-embodied-bench/vendor/graph-as-policy \
  --cap-root "$PWD/vendor/cap-x" \
  --socket /tmp/precision-commission-01.sock \
  --cues act-runs/precision-commission-01-cues \
  --output act-runs/precision-commission-01-policy --live
```

After successful commissioning, omit `--commissioning-trial` for scored collection.
For CaP select `--harness cap`; reset and use fresh paths. Observer cue and fixture
confirmation commands are in `ACT_RUNBOOK.md`. An observer confirms D2/E2/D1/E1
transfers twice in order; neither model self-reports its own cue advancement.

Sources: [physical task proposal](https://knowing-wandflower-7a9.notion.site/Task-Design-3e603e88cc6d81fcae8ae3167324b380),
[official ACT tutorial](https://docs.se3labs.ai/docs/v0.0.1/tutorials/evaluate-your-policy/act-harness/),
and the local `Precision_Long_Horizon_Memory_Proposal.md`. User overrides select
Qwen, two policies, and 450 seconds instead of that proposal's Astra/three-policy/
eight-minute pilot. No operator has been contacted by this software preparation.
