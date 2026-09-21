# Architecture and supported semantics

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

The current runtime API is synchronous `run(state, execution_id)` with one
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
