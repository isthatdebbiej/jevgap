# Select a harness for the four-harness study

The current study tests **GaP, CaP-X, ASPIRE and ENPIRE across all 13 tasks**.
Select one harness per batch and use the shared task/layout/seed matrix across
the four configurations. All four are in scope; track their readiness separately.

The batch runner accepts `harness: "native-gap"`, `"cap"`, `"aspire"` or
`"enpire"`. CaP, ASPIRE and ENPIRE run their upstream code in a separate Python
process. They do not fall back to GaP or to a local imitation.

**This is an evaluation adapter layer.** It does not supply the robot's task
implementations, reproduce every upstream development/search workflow, or make
the four methods experimentally equivalent. Commission a common pilot task
through each harness, then expand task coverage. Station credentials alone are
insufficient for any method.

## Implemented entry points

| Config selector | Upstream workflow invoked | Inputs still needed |
|---|---|---|
| `native-gap` | Pinned GaP `WorkflowExecutor`; replay or SE3 Python Policy bridge | For SE3: calibrated driver, model, station and scenarios |
| `cap` | CaP-X `capx.envs.launch.main`, headless, one trial and one worker | Native CaP-X YAML with a task environment, model/service settings and evaluator export |
| `aspire` | ASPIRE `aspire/real/run_script.py`, executing a frozen saved program | Recovered native runtime, saved policy and skill library, Hydra task/robot configuration, evaluator export |
| `enpire` | ENPIRE `enpire.env.forge.loop.TrialRunner` | Native environment and policy factories, model/checkpoint settings and evaluator export |

CaP means the named **CaP-X implementation**, not an unspecified reproduction of
the original Code as Policies paper. CaP-X may generate and repair code during
its trial. ASPIRE here evaluates an already developed policy; its skill search
and repair happen in its upstream development workflow. ENPIRE here evaluates
a supplied policy; selecting it does not automatically start neural training or
its autonomous research loop. Compare frozen-policy execution and policy
development in separate study arms; see [testing plan](TESTING_PLAN.md).

Default pins are recorded in `rtbench_tasks/upstream.py`:

- [CaP-X](https://github.com/capgym/cap-x/tree/53e9966d7a8e2fa7494676772bccc35280f5c0ed): `53e9966d7a8e2fa7494676772bccc35280f5c0ed`
- [ASPIRE](https://github.com/NVlabs/ASPIRE/tree/f4c8939aab0af9b97690c561bd80e282940f7886): `f4c8939aab0af9b97690c561bd80e282940f7886`
- [ENPIRE](https://github.com/NVlabs/ENPIRE/tree/99ee90acf65b5b18957c8382ad580db999528be3): `99ee90acf65b5b18957c8382ad580db999528be3`

Follow each repository's installation instructions in its own environment.
ASPIRE and ENPIRE document Python 3.11 setups; JevGaP's coordinator uses Python
3.12. Do not install all upstream dependencies into the coordinator environment.
Run CaP-X and ASPIRE from Linux/WSL. The pinned CaP-X runner uses POSIX signals;
ASPIRE's robotics workstation stack also needs its supported Linux environment.
Use Linux paths and Linux interpreters when running under WSL.

ASPIRE's [real-world README](https://github.com/NVlabs/ASPIRE/blob/f4c8939aab0af9b97690c561bd80e282940f7886/aspire/real/README.md)
describes workstation recovery: its fresh public clone is not self-contained.
The adapter checks for missing robot adapters, script backends and recorder
modules. Recover and validate the documented components before launching it;
these cannot be supplied by filling in a station ID. If adaptations change
tracked source, commit them locally and pin that exact revision in the profile.
Changing revisions requires rechecking the adapter's native API assumptions.

## Generate and choose configurations

After the coordinator installation in [SETUP.md](SETUP.md), run from the JevGaP
repository root (replace the Python path with `.venv-tasks/bin/python` on Linux):

```powershell
.venv-tasks/Scripts/python scripts/task_suite.py init --directory local-config/harnesses --gap-root vendor/graph-as-policy
.venv-tasks/Scripts/python scripts/task_suite.py harnesses
.venv-tasks/Scripts/python scripts/task_suite.py plan --config local-config/harnesses/enpire.local.json
```

`init` generates replay/SE3 GaP configs and `cap.local.json`, `aspire.local.json`,
`enpire.local.json`, plus 13 task-binding files for each upstream. It refuses to
overwrite a directory. If you already configured GaP elsewhere, keep those files
and point the new upstream experiments' `scenario_dir` at that calibrated
scenario directory. The generated scenario files are unconfigured templates.

Choose the harness by choosing a config file. For example, `enpire.local.json`
contains:

```json
{
  "schema_version": 1,
  "name": "enpire-stack-blocks",
  "harness": "enpire",
  "mode": "upstream",
  "tasks": ["stack-blocks"],
  "seeds": [0],
  "repetitions": 1,
  "model": {"provider": "upstream"},
  "scenario_dir": "scenarios",
  "harness_config": "upstream/enpire.local.json"
}
```

Only `native-gap` permits `mode: "replay"` or `"se3"`. Other selectors require
`mode: "upstream"`. Native model settings belong in the upstream task/policy
configuration; JevGaP rejects misleading model/budget fields in the experiment's
`model` object. The generated upstream configs inherit a `station_config` path
for convenience, but **the coordinator does not connect that file to upstream
environments automatically**. Wire station configuration into their native
environment/driver setup.

Fill in `upstream/<harness>.local.json`:

| Field | Meaning |
|---|---|
| `repo_root` | Local checkout of the selected upstream, with its native entry point |
| `revision` | Exact full commit SHA; checked against HEAD and tracked modifications |
| `python` | Executable of that upstream's installed Python environment |
| `evaluation_backend` | `se3` requires operator-session evidence; `simulation` requires simulator evidence |
| `timeout_s` | Maximum wall time for the whole native subprocess, including initialization |
| `task_config_pattern` | Binding path with `{task}`, `{seed}`, `{repetition}` placeholders |

Paths resolve relative to the file containing them. Native task YAML/Hydra
relative paths retain upstream semantics and typically resolve from the upstream
working directory. Use absolute native paths when uncertain. Config, binding and
direct native input files are hashed in each trial's provenance. Referenced
libraries, checkpoints, inherited YAML and installed task modules must also be
versioned by the experiment owner; a hash of their filename is not sufficient.

## Native task bindings

Every task/seed/repetition needs a separate binding with matching identity and
`configured: true`. Set that flag only after adapting and validating the task in
the selected upstream. It is a declaration, not proof of hardware readiness.

CaP-X binding:

```json
{
  "configured": true, "task_id": "stack-blocks", "seed": 0, "repetition": 0,
  "config_file": "/path/to/native-stack-blocks.yaml",
  "args": ["--model", "EXACT_MODEL_ID"]
}
```

The YAML must provide CaP-X's native environment (`env`) and task prompt,
grounded robot tools, model endpoint and evaluator. The environment must consume
the JevGaP scenario/seed; the native CaP trial index is always 1, so it must not be
used as the experimental seed. The adapter forces headless execution and one
trial/worker. Native retry, regeneration and feedback behavior is retained.
CaP-X distinguishes execution success from `task_completed`; both are recorded.

ASPIRE binding:

```json
{
  "configured": true, "task_id": "stack-blocks", "seed": 0, "repetition": 0,
  "program_file": "/path/to/frozen-policy.py",
  "args": ["experiment=YOUR_NATIVE_EXPERIMENT"]
}
```

Use valid Hydra overrides for the recovered upstream environment, robot adapter
and skill library. The adapter supplies `script_file`, `script_output_dir`,
`env.seed` and `hydra.run.dir`. It also treats ASPIRE's recorded execution errors
as failures even when the native process exits zero.

ENPIRE binding:

```json
{
  "configured": true, "task_id": "stack-blocks", "seed": 0, "repetition": 0,
  "environment_factory": "your_installed_task_package:make_environment",
  "policy_factory": "your_installed_policy_package:make_policy",
  "environment_kwargs": {"config_path": "/path/to/native-environment.json"},
  "policy_kwargs": {"config_path": "/path/to/frozen-policy.json"},
  "max_steps": 64,
  "args": []
}
```

Install both factory modules into the upstream environment (or keep them in its
pinned checkout). The coordinator deliberately removes its own `PYTHONPATH` from
the child environment. Factories receive exactly the declared keyword arguments.
The native Environment implements `reset(seed=...)`, `observe`, `step`, `verify`,
`close`; Policy implements `reset`, `act`, `close`. The adapter calls the actual
ENPIRE TrialRunner and retains its native result and event artifacts. Both
objects are closed after a trial, including failure paths.

## Task and evaluator export contract

Each child receives two environment variables:

- `JEVGAP_REQUEST`: JSON file with episode/task/seed/repetition, layout,
  instruction, neutral object/target IDs, correction/masking schedule, requested
  limits, backend and output directory. Private scorer `truth` is omitted.
- `JEVGAP_OUTPUT`: fresh trial directory where the trusted native environment or
  evaluator exports `evidence.json` and, for SE3, `se3-session.json`.

The trusted environment must apply the prescribed reset/layout, enforce the
chosen action/timing/memory constraints, expose only currently visible facts and
deliver corrections at the specified step. Do not feed the entire request or
correction schedule to the policy: future instructions and masked history are
environment metadata. These are environment implementation duties, not checks
that a generic subprocess wrapper can enforce. Subprocess isolation is for
dependencies and lifecycle, **not a security sandbox** for generated code.

`evidence.json` has the `Evidence` fields in `contracts.py`: `episode_id`,
`objects`, `flags`, `events`, `source`, `calibration_id`, optional `telemetry_ref`.
Facts must come from calibrated sensors/simulator state or an independent
operator, not model assertions or requested actions. See [evidence rubric](README.md#evidence-and-evaluation)
and [driver contract](DRIVER.md). Policies must not have write authority to the
evaluator channel in the deployed environment.

For `evaluation_backend: "se3"`, export this envelope from the returned SDK
session, using the request's episode ID and the actual session results:

```json
{
  "episode_id": "MATCH_THE_REQUEST",
  "state": "SUCCEEDED",
  "episodes": 1,
  "error_count": 0,
  "bridge_error": null,
  "results": [{"scored": true, "success": true}]
}
```

This illustrates the schema, not a result to copy. Retain raw SDK reports and
telemetry as well. A missing, failed, mismatched or unscored SE3 session cannot
pass. A completed trial can legitimately have task failure. Overall success
requires native execution success, native task success, independent local rubric
success and, on SE3, operator success. Simulation results are labelled separately.

## Check and run

```powershell
.venv-tasks/Scripts/python scripts/task_suite.py doctor --config local-config/harnesses/enpire.local.json
.venv-tasks/Scripts/python scripts/task_suite.py batch --config local-config/harnesses/enpire.local.json --output results/tasks/enpire-001 --live
```

Change the config filename to select another harness. Use a new output directory
for every attempt. `plan` and `doctor` do not import upstream plugins, connect to
services, or start robot/model processes. `configuration_ready` checks files,
identities and Git revision, not dependency compatibility or task performance.
The explicit `--live` is required even for an upstream simulation because native
workflows can call models or services. Agents must ask the user before a run
that spends OpenAI API credits, including calls from an upstream workflow.
The `--live` flag does not replace that approval; the CLI itself has no extra
interactive confirmation.

A subprocess timeout/exception or missing result/evidence stops the batch and
retains the attempt. The worker and its process group/tree are terminated on
timeout. Detached services and physical motion require the environment's own
watchdog and station lifecycle handling; killing Python cannot certify a stop.

Artifacts include the public request, provenance hashes, private upstream log,
process result, native result, independent evidence, per-trial row and batch
summary. Raw logs and native configs may contain sensitive station or provider
details. Keep the generated `local-config/` and `results/` directories private.
Use upstream credential files or authenticated model services, never inline
API keys in `args`.

## Validation required for four-harness results

JevGaP's `limits` are requests for upstream task ports; only the subprocess wall
timeout and ENPIRE's `max_steps` are directly enforced by these adapters. Native
GaP's Responses budget ledger does not govern upstream model calls. Match and
record native token/cost caps, retries, observation access, reset behavior,
starting skills and development budget. Freeze each policy/library and use the
same held-out layouts and evaluator. All reports remain `ranking_eligible=false`.

The committed offline tests use explicit adapter fixtures. They verify dispatch,
error handling, process cleanup and scoring boundaries; they do not run heavy
CaP-X/ASPIRE environments, prove all 13 native task ports, or claim hardware
success. Commission one task through each real upstream before expanding.
