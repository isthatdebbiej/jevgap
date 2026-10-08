# Architecture

## Current four-harness task suite

The study covers GaP, CaP-X, ASPIRE and ENPIRE on the same 13-task inventory.
`scripts/task_suite.py` loads the experiment configuration, checks readiness and
dispatches each selected task/seed/repetition through its configured harness.

| Selector | Execution path |
|---|---|
| `native-gap` | Native GaP graphs with a replay backend or the SE3 Python Policy bridge |
| `cap` | Separate upstream interpreter invoking CaP-X's headless launcher |
| `aspire` | Separate upstream interpreter invoking ASPIRE's saved-policy runner |
| `enpire` | Separate upstream interpreter invoking ENPIRE's TrialRunner and configured factories |

The coordinator records the trial matrix, provenance, attempts and outcomes.
All paths use the shared local task rubric; upstream-native outcomes and SE3
operator results are retained separately. Native environments remain responsible
for calibrated perception/control, task resets, observation exposure and measured
evidence. Upstream model budgets and development workflows require their own
configuration and validation.

See [harness entry points and contracts](../task_suite/HARNESSES.md),
[native GaP driver interface](../task_suite/DRIVER.md) and the
[four-harness testing plan](../task_suite/TESTING_PLAN.md). Adapter availability
does not establish physical readiness or a matched policy-development study.

## Historical A/B architecture and supported semantics

The following describes the earlier Astra/Jev executor experiment. Its A/B
labels and supported graph subset apply to that experiment.

```text
Observation → GaP policy graph → ActionProposal → common gate → controller
                  │
                  ├─ A: native GaP + Astra
                  └─ B: custom Rust executor + Jev
```

The graph is preserved as a policy specification in both systems. A uses GaP's
actual WorkflowExecutor, normal tracing and in-process Python functions. B
imports the supported graph subset into Rust and invokes persistent Python
workers through framed Unix-domain sockets. Each permits at most eight workers;
the measured linear graph has only one ready node at a time.

Rust readiness uses explicit `control_preconditions`, `input_bindings` and an
approved `executable`. It is not an arbitrary DAG compatibility layer. The
importer rejects ambiguous cross-frontier activation, noncausal references,
loops, conditionals, nested graphs, streams, recovery and unapproved tools.
Only the selected linear fixture has end-to-end native/Rust equivalence evidence.

The legacy runtime API is synchronous `run(state, execution_id)` with one
observation in flight. Streaming, cancellation, distributed execution and a
general asynchronous observation API are not implemented.

## Two simulation tasks

**Joint target:** independent physics advances while inference runs. The gate
validates observation identity, scene version, age, target bounds and decision
enum; it rechecks a queued proposal before dispatch. Both systems use the same
five-second age budget and control gains. Scene changes are injected and detected
at the same instant, so detector latency is excluded.

**Moving cube:** a model authorizes the shared live-state tracking controller.
After admission, that controller approaches, closes opposing fingers, lifts and
holds. It continuously observes the simulated cube; the model does not generate
servo commands. Ordinary tracking motion stays within one scene version. This
demo does not implement hardware scene-change detection or per-chunk hardware
admission. A free cube is driven along a low-friction table until contact, and
the gripper uses experimental primitive pads with frictional contacts.

Worker functions receive state dictionaries, not actuator handles. The simulator
owns MuJoCo data and force application. Inference failures cannot directly issue
robot commands. The current software boundary is not an OS security sandbox.

## Interpreting timings

A versus B changes scheduler, tracing, process model, IPC and model inference.
Do not attribute the result to Rust alone. Raw workflow events record input/output
and timing; Rust also records eligibility, dispatch, worker and return times.
Native GaP does not yet expose equivalent detailed eligibility timestamps.

Neither task requires a semantic model to solve. These runs establish plumbing
and response behavior. A frozen, labeled semantic evaluation and an appropriate
original expensive decision worker are still required for meaningful inference
quality claims.
