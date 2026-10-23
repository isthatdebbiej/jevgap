# Current entry point

Use [OPERATOR_HANDOFF.md](OPERATOR_HANDOFF.md) and `operator-packet-v3` for the reconciled tasks, full scoring, $230 budget and 52-request episode limit. The examples below supply observer commands; the current launch requires `--packet operator-packet-v3`, with `--commissioning-trial` only for supervised commissioning.

# ACT runner: current implementation and launch

The selected controller is the official SE3 ACT Harness. No custom semantic
`grasp`/`place` driver is required. The open model receives all three cameras and
chooses Cartesian moves, rotations and gripper actions. The SDK supplies YAM
kinematics and motion profiles. Astra configuration is retained.

## Verified

- Both actual native runners completed a two-turn diagnostic with a fake ACT
  endpoint and canned model responses.
- Both actual native runners completed a real `Qwen/Qwen3.8-27B` image request
  against a fake ACT endpoint. Each made one model request, chose to end the
  diagnostic episode, and sent zero motion commands.
- Twenty-five Linux ACT tests passed: images, bounded commands, stale/wrong-episode
  telemetry, task identity/scoring separation, service wiring and hidden cues.
- These are software checks, not successful manipulation episodes.

Evidence: `act-model-validation-generated-v2/gap/validation.json` and
`act-model-validation-generated-v2/cap/validation.json`, with model usage and frame records.

## Launch one episode (Ubuntu/WSL)

Use two terminals. The service submits one episode and exits after scoring;
it does not reconnect or launch another task automatically. Use fresh output,
socket and cue paths for every episode. For a matched pair, reset the physical
layout, restart the service, and change `--harness native-gap` to `--harness cap`.

```bash
cd '/mnt/c/Users/dshek/OneDrive/Documents/ChatGPT/GaP'
export PYTHONPATH="$PWD/task_suite"
.venv-linux/bin/python -m rtbench_tasks.act_run serve \
  --packet operator-packet-v3 --commissioning-trial \
  --task operator-packet-v3/tasks/precision-memory-delayed.json \
  --socket /tmp/gap-precision-01.sock \
  --output act-runs/gap-precision-01-service \
  --auth-file /mnt/c/Users/dshek/.se3labs/production.json \
  --station se3-labs-yam-2 --address 100.107.161.92:7443 --live
```

```bash
cd '/mnt/c/Users/dshek/OneDrive/Documents/ChatGPT/GaP'
export PYTHONPATH="$PWD/task_suite"
.venv-linux/bin/python -m rtbench_tasks.act_run agent \
  --task operator-packet-v3/tasks/precision-memory-delayed.json \
  --model act-config/qwen.json --harness native-gap \
  --gap-root /mnt/c/Users/dshek/Work/Robotics/rt-embodied-bench/vendor/graph-as-policy \
  --cap-root "$PWD/vendor/cap-x" \
  --socket /tmp/gap-precision-01.sock \
  --cues act-runs/gap-precision-01-cues \
  --output act-runs/gap-precision-01-policy --live
```

The agent waits up to 60 seconds for a live rollout. Start it when the station
operator is ready to begin. The service's task sheet asks the operator to
prepare/reset and score the scene. Its rollout limit is **450 seconds**, not
the stock ACT example's 600 seconds. The controller uses the SDK start pose
`(0, 1.5, 1.5, 0, 0, 0)` for both arms; confirm this with the operator before
starting. Camera and action records remain in the episode output directories.

The model profile references the existing private key file without copying it.
Its shared reservation ledger enforces the user-approved $230 reservation ceiling at $0.10 per request. Both native runners allow at most 52 decisions per episode. Failed calls retain their reservations. This is reservation accounting rather than a provider billing statement. See the handoff for the complete plan and remaining budget.

## Precision/memory observer cues

Five cubes A/B/C/D/E, arrows, T1/T2/T3 and D1/D2/E1/E2 are required. A single A
cube is insufficient. The initial job is presented once. Later observations
contain only the current transport/correction/final-execute cue; memory belongs
to the policy. A separate observer confirms each stable D/E transfer, not the
model itself. Obtain the episode UUID from `robot/events.jsonl` or ACT status:

```bash
.venv-linux/bin/python -m se3labs.sdk.examples.act_harness \
  --socket /tmp/gap-precision-01.sock send status
```

Use the service socket with the SDK's `Harness(socket_path).status()` API, or
read `episode_id` from the policy event log. Then, for the first observed
completed transfer:

```bash
.venv-linux/bin/python -m rtbench_tasks.act_cues \
  --directory act-runs/gap-precision-01-cues --episode-id ACT_EPISODE_UUID \
  --transfer 1 --object D --target D2
```

The eight confirmations are, in order: D→D2, E→E2, D→D1, E→E1, repeated once.
Do not prefill confirmations. A confirmation records an observer judgement;
it is not a calibrated 10 mm / 10 degree measurement. The correction variant
issues its correction once after transfer two. Stale episode IDs and duplicate
confirmations are rejected. Observer cue operation is additional to SE3's
normal final scoring; it is not fully autonomous cue verification.

## Scoring and physical limits

The full reconciled task definitions, independent progress/quality scoring and
measurement procedure are in OPERATOR_HANDOFF.md. CaP's three-file import
adaptation and native source pins are preserved and verified before use. Its
Python environment restricts imports/file access/private attributes but is not
an OS sandbox. Shared ACT commands limit each translation to 5 cm and rotation
to 30 degrees per axis; this is not a table/collision model. Original frames
are retained and model images are resized to 320x180; label readability must
be checked during station commissioning. Execution success is not task success.

## Moving-cube observer step

After `fixture-request.json` appears in that episode's cue directory, confirm
the robot is stopped and physically clear. Perform only the prescribed A-cube
relocation, lock the fixture, then run:

```bash
.venv-linux/bin/python -m rtbench_tasks.act_fixture \
  --directory act-runs/gap-precision-01-cues \
  --socket /tmp/gap-precision-01.sock --arm-clear --locked
```

The withheld command is discarded. Only a new policy decision after fresh
post-lock images may move the robot. The prescribed intervention is excluded
from the manual-assistance failure criterion. Do not prefill this confirmation.

## Operator invitation gate

Offline implementation and scoring are complete. Bring the operator for
commissioning using OPERATOR_HANDOFF.md. Scored collection is gated on the
operator's recorded physical checks and calibration; no physical readiness is
inferred from software tests. Older READINESS-pre-ACT.md describes a superseded
controller path. Packets v1/v2 are superseded by operator-packet-v3.
