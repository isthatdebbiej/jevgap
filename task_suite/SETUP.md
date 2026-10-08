# Native GaP / SE3 setup

The batch runner covers all 13 task contracts. The SE3 SDK bridge and Responses
model adapter can be tested offline. **Physical testing still needs a calibrated
station driver implementing perception, motion and independent verification.**
Station IDs alone do not provide those capabilities. See [driver contract](DRIVER.md)
and [remaining work and comparison design](TESTING_PLAN.md).

For configurable CaP-X, ASPIRE and ENPIRE upstream adapters, see
[harness setup](HARNESSES.md). `init` now creates templates for all four harnesses.

## Install and create configuration

From the JevGaP repository root, use Python 3.12 and the GaP checkout pinned by
`gap-commit.txt`. The existing setup script obtains that checkout. A separate
environment avoids changing the historical moving-cube demo's dependencies:

If `python` opens the Microsoft Store on Windows, install/use an actual Python
3.12 interpreter first, and substitute its full executable path in the first
command. Creating configuration does not install the required environments.

```powershell
python -m venv .venv-tasks
.venv-tasks/Scripts/python -m pip install -e "./task_suite[native,se3]"
.venv-tasks/Scripts/python scripts/task_suite.py init --directory local-config/se3 --gap-root vendor/graph-as-policy
.venv-tasks/Scripts/python scripts/task_suite.py doctor --config local-config/se3/replay.json
.venv-tasks/Scripts/python scripts/task_suite.py batch --config local-config/se3/replay.json --output results/tasks/replay-001
.venv-tasks/Scripts/python scripts/check_tasks.py
```

On Linux, use `.venv-tasks/bin/python`. If GaP has not been fetched, clone
`https://github.com/graph-robots/graph-as-policy.git` into `vendor/graph-as-policy`
and check out the commit in `gap-commit.txt`. No robotics submodules are needed
for these offline graph checks. The preflight rejects a different commit.

The equivalent installed command is `rtbench-tasks experiment ...`.
`init`, `doctor`, replay batches and tests make no model requests or station
connections. `init` refuses to overwrite an existing directory and writes an
ignore file to protect local settings. Every batch also requires a new output
directory. Replay uses known answers and synthetic evidence: its passing scores
test software contracts, not physics, model quality or robot performance.

## Files to fill in later

| Generated file | Settings |
|---|---|
| `station.local.json` | SE3 `station_id`, relay `address` (`host:port`), `calibration_id`, approved `start_pose`, `driver_factory`, `driver_config`, `validated_tasks`, per-task operator `reset_instructions` |
| `se3.local.json` | Exact API `model_id`, private `key_file` path, dedicated budget ledger and allowances, selected tasks, seeds, repetitions, time/decision/memory limits |
| `scenarios/<task>--<seed>--<repetition>.json` | Unique episode ID, calibrated layout, initial instruction, neutral IDs, private evaluation truth, optional corrections and masking |
| `driver.local.json` | Create this using your driver implementation's schema; camera/extrinsic calibration, object geometry, robot limits, controller settings and evaluator thresholds belong here |

Paths inside experiment files are relative to that experiment file, independent
of the current directory. `driver_config` is relative to the station file.
`key_file` contains the API credential; do not put keys or SE3 tokens in JSON.
The SE3 SDK uses the login saved by `se3labs auth login`. Its relay connection
uses the operator-provided Tailscale network. Arrange the account email,
Tailscale access and station reservation directly with SE3 when ready.

`start_pose` maps every station arm name to `{"joints": [...], "gripper": [...]}`.
Joints are absolute radians; gripper values are fractions in [0, 1]. Obtain
actual names, dimensions and approved poses from the station; no default pose
is supplied. The driver must approve the initial motion as well as later plans.

The generated physical scenarios are **templates copied from diagnostic fixtures**.
Replace the `UNCONFIGURED-physical-layout`, truth and object/target definitions
with the actual setup. A seed is an identifier for a prescribed layout, not a
physical randomizer. Additional seeds or repetitions require matching scenario
files, each with a distinct ID and reset procedure. Keep held-out layouts away
from policy development and public observations.

Add a task to `validated_tasks` only after its driver, props, perception and
evaluation predicates have been exercised at the station. This is an operator
declaration, not something `doctor` can independently verify. For
`press-by-number`, confirm the task source's ambiguous confirmation sequence
with SE3 before setting `press_protocol` and scenario `truth.protocol` to
`two-stage-v1`.

## Preflight and physical runs

```powershell
.venv-tasks/Scripts/python scripts/task_suite.py doctor --config local-config/se3/se3.local.json
```

Exit code 2 lists missing configuration. `configuration_ready=true` means the
offline checks passed; `hardware_validated` remains false. Preflight does not
import a driver, log in, contact a model, test connectivity or execute motion.
Freeze numeric geometry/timing tolerances and the driver implementation before
collecting results. Start with a single validated task and one scenario.

Once the driver and station have been commissioned, the explicit live command is:

```powershell
.venv-tasks/Scripts/python scripts/task_suite.py batch --config local-config/se3/se3.local.json --output results/tasks/se3-001 --live
```

This command can spend API credits and move the robot, including the configured
initial pose. SE3 runs one job per scenario. The operator resets and scores each
episode. An integration failure stops the batch, records the failed attempt and
leaves remaining trials unattempted. No automatic motion retry or batch resume
is implemented; reconcile the station and use a new output directory.

## Model settings and budgets

The implemented live provider is `openai-responses`, with strict structured
`action` + `memory` output. Set an exact available model ID. If the provider
returns a dated snapshot name for an alias, explicitly list acceptable IDs in
`accepted_response_models`. An unexpected model, refusal, incomplete output,
malformed action or missing usage fails the call. There is no fallback model.
Legacy Jev enum decisions are a different contract and are not accepted here.

`budget_usd` and `reservation_usd` start at zero, deliberately blocking requests.
Every attempted request atomically consumes its full reservation in a dedicated
SQLite ledger shared across trials and invocations. Failed/uncertain calls keep
their reservation; there are no automatic retries. Existing ledgers from the
historical provider are rejected, so their spending cannot silently disappear.

These are **reservation allowances, not a measured invoice or a guaranteed
provider spending cap**. Choose a conservative per-call upper bound using current
model pricing, the complete prompt/schema overhead, `max_input_bytes`, and
`max_output_tokens` (including reasoning). Configure provider-side limits as
appropriate. Actual token usage and returned model IDs are recorded separately.
Do not delete or change ledgers between cells to bypass the study budget.

Model requests are stateless. Only the current public observation, instruction
(unless masked), scheduled correction, public feedback and explicit bounded
memory are supplied. Hidden conversation history is not used. This adapter
sends structured text; image URLs in an observation are not automatically fetched
or encoded as vision inputs. The driver must supply grounded visible facts.

`max_age_ms` includes model latency: a decision may be rejected if its input has
aged before dispatch. Measure latency and choose the experimental freshness
limit explicitly. Increasing a limit does not validate a dynamic scene. Driver
planning must still check current geometry and object identity.

## Artifacts and interpretation

Each batch saves a configuration hash, pinned GaP revision, generated graphs,
trial matrix and per-trial status. Episode directories contain the graph trace,
decision/command events, local report, private evidence and, for returned SE3
sessions, operator score records and deployment configuration hashes. Keep
evidence and traces private until reviewed; they can contain task instructions,
camera references and station details. Never publish generated configuration.

Session completion, graph completion, local score and operator success are
separate. Overall success requires a completed single-episode session, a scored
operator success, measured local success and an explicit policy `finish`.
Unscored, cancelled or failed sessions never pass. Operator binary judgement
does not replace the local task's partial-credit rubric. All current reports
remain `ranking_eligible=false` and `official_submission=false`.

The implementation follows the [SE3 Python API tutorial](https://docs.se3labs.ai/docs/v0.0.1/tutorials/evaluate-your-policy/python-api/)
and pinned `se3labs==0.0.1` / `se3labs-interface==0.0.1` contracts. The
[XPolicyLab tutorial](https://docs.se3labs.ai/docs/v0.0.1/tutorials/evaluate-your-policy/xpolicylab/)
is a separate deployment/model-server route. The native GaP path uses the Python
Policy API directly and does not need an XPolicyLab model server.
