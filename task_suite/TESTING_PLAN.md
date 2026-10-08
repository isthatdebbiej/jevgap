# JevGaP four-harness testing plan

Scope: **GaP, CaP-X, ASPIRE and ENPIRE across all 13 tasks**. All four harnesses
are included in the current testing program. Choose the harness in configuration
and assess every harness against the same task definitions, prescribed layouts
and independent evaluator.

The planned matrix contains **52 harness/task combinations**, multiplied by the
selected layouts, seeds and repetitions. Record readiness and outcomes for each
combination, including blocked or unsupported cases. A blocked integration stays
visible in the matrix; it is neither a completed trial nor evidence of task failure.

Evaluation adapters and offline integration checks are implemented. Physical
task readiness, complete policy-development workflows and matched experimental
budgets still require validation. Study scope does not imply equal implementation
readiness or a completed reproduction of each upstream research system.

## 1. Software integration — implemented

- [x] Thirteen source-linked task contracts, native GaP graphs and skill declarations.
- [x] Local scoring with private evidence, explicit per-episode memory and known-answer replay fixtures.
- [x] Config-generated experiment matrix, offline preflight, fresh output directories and retained failures.
- [x] SE3 0.0.1 Python lifecycle bridge, validated joint-chunk structure, measured-completion interface and cancellation handling.
- [x] Stateless Responses model adapter, explicit model checking, token records and persistent request reservations.
- [x] Offline tests through all 13 native graphs and all 13 SDK callback lifecycles, plus failure paths.
- [x] Separate CI job for the task suite; historical Rust/moving-cube checks remain separate.
- [x] Configurable upstream CaP-X, ASPIRE saved-policy and ENPIRE TrialRunner adapters with pinned profiles, all 13 task-binding templates, preflight, process limits and separate native/local/operator outcomes. See [harness guide](HARNESSES.md).

These graphs are supplied scaffolding that route model-selected semantic actions.
They do not currently test an AI coding agent generating or repairing graph
structure, code or learned weights. Replay runs use recorded correct actions and
synthetic evidence. Both distinctions must appear in any result description.

## 2. Station commissioning — requires SE3 access and calibration

Owner: SE3 operator plus the station integration engineer.

- [ ] Create the SE3 account using the chosen email; configure saved SDK login and Tailscale.
- [ ] Supply station ID/relay address; check arm and camera specs and approved initial pose.
- [ ] Implement or connect calibrated perception, control and independent evaluation for each harness; use the [native GaP driver contract](DRIVER.md) and [upstream environment contract](HARNESSES.md#task-and-evaluator-export-contract).
- [ ] Freeze robot/camera calibration, object geometry, tolerances, software revisions and operator reset instructions.
- [ ] Check SDK hold-still/start-pose behavior, timestamps, disconnect, rollout timeout, cancellation and station stop behavior.
- [ ] Connect each harness's native environment/task binding to the calibrated station and evaluator.
- [ ] Run a supervised Stack Blocks pilot through each of the four harnesses; compare independent local and operator scoring and inspect recordings.

Acceptance: no stub controller, synthetic evidence or fixture layout is used;
commands have measured effects; failures stop progression and retain artifacts.
Keep each combination blocked until its native task binding, calibrated scenario
and operator validation are complete. Use the [harness setup](HARNESSES.md) and
[native GaP SE3 configuration](SETUP.md) for the corresponding file fields.

## 3. All 13 tasks — validate capabilities in this order

Owner: integration engineer for control/perception and native task ports;
evaluator owner for ground truth; station operator for props, layout and reset.
Apply this capability sequence to all four harnesses. All tasks also need
measured return-home and gripper-release checks.

| Order | Tasks | Additional capability / evidence to validate |
|---|---|---|
| A | Stack Blocks, Stack Bowls | Stable grasp/stack, support topology, bowl nesting and upright orientation |
| B | Pack Objects into Box, Classify Objects, Classify Objects by Language | Containment, front orientation, category/basket mapping, corrected instructions and masked-memory conditions |
| C | Arrange Largest Number | Digit recognition, neutral tile identity and measured ordered-pad placement; test both four and five tiles |
| D | Cover Blocks | Cover/uncover control, actual occlusion, persistent explicit memory and independently observed event order |
| E | Hang Mugs, Play Stacking Toy | Handle/hook geometry, group counts and peg/base placement |
| F | Press by Number | Counted contact events; resolve source prose versus scoring-table confirmation sequence with SE3 |
| G | Insert Tubes, Plug in Charger | Contact-aware alignment and measured insertion depth; agree the unpowered dummy charger adaptation |
| H | Align Blocks | Set-square manipulation, pushing, alignment tolerance and continuous proof of no lifting |

The fabricated A–H cubes help cube experiments but do not provide bowls, mugs,
number tiles/buttons, covers, containers, tubes, sockets, stacking toys or a
set square. Inventory and geometry are therefore separate commissioning items.
The linked page enumerates 13 simulation tasks originally described for ARX X5;
YAM runs are adaptations. Freeze those differences in the experiment record.

For each task, exercise successful, partial-credit and deliberately failed
outcomes; compare operator and local scores; verify an occluded or missing
measurement cannot earn credit. Run the selected task matrix for each harness
through the batch runner with operator-prescribed resets. One successful episode
per harness/task combination demonstrates feasibility only. Choose repeat counts
after estimating failure rates and runtime from the pilots; do not infer rankings
from a single episode per combination.

## 4. Research design — all four harnesses

Evaluate **GaP, CaP-X, ASPIRE and ENPIRE** using a shared task matrix. Commission
the pilot task for each harness and expand task coverage as its native bindings
are validated. The four systems expose different execution and development
workflows, so record the exact workflow, policy representation and initial skill
library used in each study arm. Control resources before drawing comparisons.

| System | What it contributes | Experimental role |
|---|---|---|
| [GaP](https://github.com/graph-robots/graph-as-policy) | Typed computation graphs, modular skills and execution checkpoints | Evaluate native graph execution; connect graph generation/repair for the development arm |
| [CaP-X](https://github.com/capgym/cap-x) | Python policy programs; CaP-Agent0 includes multi-turn feedback and synthesized skills | Evaluate the configured native generation/execution workflow; declare feedback and regeneration budgets |
| [ASPIRE](https://github.com/NVlabs/ASPIRE) | Iterative program repair and reusable skill discovery; includes search/transfer experiments | Evaluate saved policies through the current adapter; connect repair/search and control the initial library for the development arm |
| [ENPIRE](https://github.com/NVlabs/ENPIRE) | Physical reset, rollout, verification and iterative policy improvement; supports heuristic code and neural training | Evaluate supplied policies through TrialRunner; connect development workflows and measure improvement per trial/time/compute budget |

Use two complementary study arms across the four harnesses:

1. **Policy evaluation:** measure task success, recovery, auditability and
   latency for each harness under matched observations, control and feedback.
   Freeze policy artifacts and libraries for an execution-only comparison.
   CaP-X's current launcher can generate/repair code during a trial, so record
   those calls as development and isolate frozen execution before claiming a
   matched execution-only result. Ablate checkpoints, explicit memory and skill
   reuse where supported, and label unsupported ablations.
2. **Agent-led development:** measure how each harness produces policies that
   generalize to held-out layouts under equal development budgets. Give all four
   the same development tasks, initial primitives, feedback and model. Log every
   edit and trial; freeze the resulting code/graphs/library before evaluation.
   Connecting the complete upstream development workflows is remaining work.

Use task/layout/seed blocks and randomize harness order to control station drift.
Reserve development and held-out scenarios in advance. Use multiple independent
development runs, not just many evaluation episodes from one optimized policy.
For cross-task skill transfer, hold out entire tasks and state the curriculum;
prevent skills trained on held-out tasks leaking into the initial library.

Match robot, perception, controller limits, model/version, instruction exposure,
action/decision caps, per-episode time, explicit memory, calibration and evaluator.
For the improvement study also match model tokens/cost, robot episodes, wall time,
compute and permitted human intervention. Publish differences that cannot be
matched. Count reset time, setup failures, aborts and manual interventions.

Report full-success rate, partial score, completion time, calls/tokens/cost,
recovery after perturbation, operator intervention and score disagreements.
For improvement, report held-out performance versus consumed development trials
and budget. Use confidence intervals and paired task comparisons; repeated
episodes from one policy are not independent development runs.

Code/graph/skill refinement is different from neural-weight fine-tuning.
Evaluate frozen-model code improvement first. A later weight-training study
needs dataset/version tracking, train/validation/test separation, training
budgets and frozen checkpoint evaluation; it is not implemented by this runner.

## 5. Remaining implementation and study validation

- [ ] Common agent-development interface: propose/edit, validate, run, inspect traces, revise; immutable artifacts for each revision.
- [x] Multi-harness selection, trial manifests, native subprocess invocation, failure preservation and score normalization.
- [ ] CaP-X task environment ports with the shared grounded primitive API and specified feedback mode; native launcher adapter is implemented.
- [ ] ENPIRE and ASPIRE task/station ports and complete policy-development workflows; evaluation adapters are implemented, full search/repair/training reproduction is still separate work.
- [ ] Cross-harness development budget enforcement, frozen evaluation protocol and paired aggregation with confidence intervals.
- [ ] Optional providers for Jev/other models using the action-and-memory contract; verify exact model identity and usage accounting.
- [ ] Optional XPolicyLab path if deploying a separate model server becomes useful; do not implement it merely to duplicate the working Python API route.

The legacy Jev/Rust executor supports a smaller graph subset and cannot stand
in for native GaP on these looping task graphs. Keep executor and model
comparisons separate from the four-harness research question.

## Completion criteria

Offline integration is complete when the suite passes without credentials and
the generated physical template fails preflight for the documented missing
inputs. Physical readiness requires successful commissioning and independently
checked evidence for each of the 52 harness/task combinations. A research
comparison additionally requires a complete coverage/status matrix, frozen
baselines, equal budgets, held-out trials and statistical analysis. Report any
blocked combinations explicitly when publishing an incomplete study.
Current artifacts intentionally make no leaderboard or four-harness ranking claim.

Sources: [task inventory](https://knowing-wandflower-7a9.notion.site/Task-Design-3e603e88cc6d81fcae8ae3167324b380),
[SE3 Python API](https://docs.se3labs.ai/docs/v0.0.1/tutorials/evaluate-your-policy/python-api/),
[SE3 XPolicyLab](https://docs.se3labs.ai/docs/v0.0.1/tutorials/evaluate-your-policy/xpolicylab/),
and the primary repositories linked in the comparison table. Reviewed October 2026.
