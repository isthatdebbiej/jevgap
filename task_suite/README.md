# SE3 thirteen-task suite

All 13 tasks on the hardware team's [Task Design page](https://knowing-wandflower-7a9.notion.site/Task-Design-3e603e88cc6d81fcae8ae3167324b380) now have task contracts, native GaP graphs, skill declarations, local scoring and known-answer replay fixtures. The task-specific sources are recorded in `rtbench_tasks/catalog.py` and every run report.

**Status:** native graph/replay execution, a configurable batch runner, a stateless Responses model adapter and the SE3 0.0.1 Python lifecycle bridge are implemented and tested offline. Physical execution requires an explicitly enabled run and a calibrated station driver; perception, motion controllers and physical evaluation have not been validated. Replay success is not robot success or a model benchmark result.

Start with [configuration and setup](SETUP.md), the [station driver contract](DRIVER.md), and the [plan for all 13 tasks followed by the four-harness comparison](TESTING_PLAN.md).

## Run

Use Python 3.12 and the project's pinned `vendor/graph-as-policy` checkout. From this directory:

```powershell
python -m pip install -e ".[native,se3]"
python -m rtbench_tasks list
python -m rtbench_tasks replay --gap-root ../vendor/graph-as-policy --output outputs/pilot-check
$env:GAP_ROOT = (Resolve-Path ../vendor/graph-as-policy).Path
python -m unittest discover -s tests -v
```

Use an unused output directory for each trial; existing trial records cannot be overwritten. If this package is inside the assembled repository, `--gap-root` is detected automatically. `build` writes 13 validated workflow graphs, nine reusable skill bundles and checkpoint sidecars without running any episode. No model calls or paid credits are used by `list`, `build`, tests or `replay`.

## Tasks and hardware implications

| Task | Operation / props | Local score levels |
|---|---|---|
| Stack bowls | Three upright nestable bowls | 0, 15, 100 |
| Pack objects into box | Four front-marked objects, aligned box; fronts face left | 0, 10, 25, 50, 100 |
| Hang mugs | Three mugs and rack | 0, 15, 40, 100 |
| Arrange largest number | Four or five single-digit tiles and ordered pads | 4 tiles: 0, 5, 15, 30, 100; 5: 0, 5, 15, 25, 40, 100 |
| Stack blocks | Three textured blocks | 0, 15, 100 |
| Cover blocks | Three colored blocks and opaque covers; cover left-to-right, uncover R/G/B | 0, 5, 15, 30, 100 |
| Press by number | Two number cards, two red buttons, blue confirmation | 0, 100 |
| Plug in charger | Unpowered dummy plug/socket for a clean hardware adaptation | 0, 100 |
| Insert tubes | Three empty dry tubes and rack | 0, 20, 40, 100 |
| Classify objects | Three categories, three baskets; assignment may vary | 0, 15, 40, 100 |
| Play stacking toy | Four pegs; corresponding groups of 4/3/2/1 pieces | 0, 10, 30, 60, 100 |
| Align blocks | Push three blocks with a set square; never lift blocks | 0, 100 |
| Classify objects by language | Three categories into instructed left/middle/right baskets | 0, 10, 40, 100 |

The official descriptions do not specify numeric alignment, insertion, stability or orientation thresholds. SE3 must freeze those calibration values and how they are measured before scoring hardware. This package requires an evaluator/calibration identifier and explicit measured predicates; it does not invent official tolerances. All tasks require the robot to return to origin for 100 points.

`press-by-number` explicitly requires `truth.protocol = "two-stage-v1"`, following the task's scoring table: first count, confirm, second count, confirm. Its prose suggests a different confirmation sequence. Resolve this with SE3/upstream before collecting experimental results.

## Graph, skills and tool catalog

Each native graph loops through `se3.observe` → `se3.decide` → the selected skill subgraph → an independent checkpoint → observation. The model selects the object, target and orientation; the harness does not copy a ground-truth target into the action. `finish` and `abort` terminate. A fixed call cap bounds the loop.

The reusable `se3-place`, `se3-stack`, `se3-hang`, `se3-cover`, `se3-uncover`, `se3-press`, `se3-insert`, `se3-push` and `se3-home` bundles contain `SKILL.md` contracts and canonical typed scripts. The harness loads them through GaP's `SkillsRegistry`, registers its bound functions in `ToolRegistry`, and executes through the native `WorkflowExecutor` with `checkpoints="raise"`. Each manipulation invokes `se3.dispatch` once. Unknown or failed completion stops the graph without retrying motion.

The model receives the same task-appropriate semantic skill catalog for every provider. Catalog availability does not imply that a robot implements that skill: backend capabilities are checked separately. These bundles depend on the harness-provided `se3.dispatch` tool and cannot control a robot by themselves.

## Connect a model and simulator

Implement the interfaces in `contracts.py` and call `runtime.run_episode`, or use:

```powershell
python -m rtbench_tasks run --scenario scenarios/trial.json --model EXACT_MODEL_ID --policy lab_provider:make_policy --backend lab_sim:make_backend --output outputs/trial
```

`make_policy(model_id=...)` returns a fresh policy with that exact model id and `decide(request)`. `make_backend()` returns a fresh backend. No fallback model is selected. This extension interface can accommodate additional providers. The built-in SE3 batch path currently implements OpenAI Responses only; existing enum-only decision providers need an adapter to the new action-and-memory response contract. Response-model verification, token accounting and request reservations are implemented in `responses.py`. The generic `run` command remains restricted to replay/simulation backends; use the configured batch command for SE3.

The provider returns exactly `{"action": {"skill": ..., "object_id": ..., "target_id": ..., "orientation": ...}, "memory": "..."}`. Memory persists only within the episode, has a fixed size cap, and is updated by the model. All providers must use identical prompt visibility, memory limits, action budgets and matched scenarios. A provider must not retain a hidden conversation outside these explicit inputs when masking is enabled.

A private scenario records task id, seed, layout id, neutral object/target ids, initial instruction, private evaluation truth, optional `(decision_index, text)` corrections, and optional `mask_instruction_after`. Corrections are shown at their scheduled decision; the model must retain them in memory. Private truth must already describe the corrected scoring target when a correction changes the goal. Instruction text, category assignments and hidden object attributes are never reconstructed for the model from scorer truth. See `replay.fixture` for all 13 scenario formats.

The backend must provide:

1. Calibrated observations, with monotonically increasing sequence ids and locally mapped monotonic capture timestamps. Remove occluded attributes and avoid identity-bearing ids in memory tasks. Camera references can be supplied in the public observation; no image encoder is supplied here.
2. Semantic skill execution, fresh-observation checking, command ids, completion feedback and its own controller safety constraints. The harness rejects stale observations before dispatch; `--max-age-ms` is an explicit experimental setting, not an automatically relaxed limit.
3. Independent command-effect verification, distinct from a command acknowledgement or model assertion.
4. Private `Evidence` measured from simulator state or calibrated human/vision evaluation, including observed event order for cover/press tasks and continuous no-lift evidence for alignment. Scoring never infers achieved placements from commanded actions.

The current YAM station pickup runner remains separate. Its red-cube detector and single-pickup command cannot implement these tasks. Keep its existing observation, completion and actuator guards when adding an SE3 connector. A `.rrd` recording is useful evidence but is not a live command interface.

## Evidence and evaluation

`Evidence.objects` maps neutral object ids to measured facts. The scorer uses `support`, `container`, `settled`, `upright`, `orientation_valid`, `hung`, `pad_index`, `covered`, `depth_valid`, `at_base` and `aligned`, as applicable. `flags` include `robot_home`, `gripper_open`, `box_aligned`, `cups_orientation_valid`, `alignment_valid`, `no_lift_entire_episode` and `used_set_square`. Missing facts earn no credit. The sensor/operator adapter is responsible for deriving these facts from calibrated geometry and telemetry. This is not yet a geometric evaluator or RRD parser.

This local rubric conservatively requires release at all intermediate tiers and stable objects where appropriate. These choices, and the unpowered charger adaptation, must not be presented as exact upstream evaluator equivalence. The official simulator evaluator remains authoritative for a future submission.

Each trial writes `report.json`, public decision/command `events.json`, private `evaluation.json`, and native GaP traces. Reports record model, seed, layout, graph/scenario hashes, limits, source page, checkpoints, stop reason, score and optional RRD reference. A completed graph and a successful task are reported separately. All reports currently set `ranking_eligible=false` and `official_submission=false`.

The current priority is all 13 tasks with native GaP, then a four-harness comparison. Start with one commissioned task before expanding the physical batch to all 13. A single run per task is a feasibility check; repeated held-out trials are needed for a research result. Layout labels in replay fixtures are identifiers, not calibrated physical placement plans.

Future [RoboDojo submission](https://robodojo-benchmark.com/leaderboard/protocol) still requires the official evaluator, required robots/seeds and submission artifacts. No XPolicyLab transport, official simulator assets or leaderboard integration is claimed by this pilot package.
