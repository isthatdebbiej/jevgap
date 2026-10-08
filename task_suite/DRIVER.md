# Calibrated SE3 driver contract

`rtbench_tasks.se3.GraphPolicy` adapts native GaP episodes to SE3 0.0.1's
`initialize` / `infer` / `reset` lifecycle. It does not implement a robot-specific
planner, detector, grasp controller or geometric evaluator. Those components
must be supplied as a trusted station driver. Test fixtures are not deployable
drivers and must never be used with hardware.

Configure `driver_factory` as `your_package.se3_driver:create_driver` and
`driver_config` as a local calibration/config file. The factory is called with
`config_path=...` and returns a **fresh** driver per episode. It must not move the
robot or open a second command channel. All requested motion passes through
SE3 action chunks. Its `calibration_id` must exactly match station configuration.

## Interface

| Member | Required behavior |
|---|---|
| `calibration_id: str` | Immutable identity of the validated sensor, controller and scoring calibration |
| `capabilities: set[str]` | Implemented semantic skills: applicable subset of `place`, `stack`, `hang`, `cover`, `uncover`, `press`, `insert`, `push`, plus `home` |
| `validate_station(station)` | Check actual arm/camera names, dimensions, rates and calibration against the station spec; reject unsupported hardware |
| `validate_start_pose(pose)` | Approve SDK initial pose and its station-managed move; check workspace, limits and collision assumptions |
| `reset(scenario)` | Clear episode-local state, measurement history and prior goals; initialize the evaluator without issuing motion |
| `observe(raw) -> dict` | Produce current public facts from the raw SDK observation; exclude evaluator truth and occluded attributes |
| `plan(action, raw) -> JointPlan` | Ground the requested semantic object/target in the latest observations; produce a complete bounded absolute trajectory for every arm |
| `validate_plan(action, plan, latest_raw)` | Recheck identities, geometry, feasibility, velocity/contact limits and scene drift immediately before submission; raise on uncertainty |
| `verify(action, command_id, raw) -> Verification` | Return `pending`, `completed` or `failed` using measured effects on later observations; feedback must contain only public facts |
| `evidence() -> Evidence` | Return private measurements/history for independent scoring, matching episode and calibration IDs, plus telemetry reference |
| `close()` | Bounded cleanup, no new motion; tolerate cleanup after partial initialization |

`JointPlan(arms={name: (joint_rows, gripper_rows)}, rate=...)` uses `[horizon,dof]`
arrays, absolute radians and gripper fractions in [0, 1]. All arms share the
same nonzero horizon and sample rate. The bridge checks finiteness, shapes,
names and the SDK control-rate limit. The driver remains responsible for
joint/velocity/acceleration bounds, collision geometry, contact/force limits and
behavior when a grasp or insertion fails. Do not implement contact tasks with
an unvalidated generic straight-line trajectory.

The bridge publishes observations on the SDK callback thread. Driver reset,
observation interpretation, planning, verification and evidence run on one GaP
worker. `validate_plan` runs under the bridge lock, so it must be bounded and
fast. `close` may run after cancellation while that worker is finishing: it
must synchronize its own resources. A slow provider may outlive cancellation;
the closed bridge refuses later commands and the batch records an error.

## Completion, clocks and cancellation

One motion can be unresolved at a time. Returning an action chunk or waiting its
nominal duration is not completion. Verification must use a later observation,
confirm the robot has settled and measure the intended effect. For example,
reaching a grasp pose is not proof that a mug is hanging. A failed or unknown
effect stops the episode rather than issuing a duplicate command.

SE3 chunk timestamps are station timestamps from the frame used to plan; local
wall time is never substituted. The bridge rejects backwards arm clocks,
unsynchronized arm observations, duplicate freshness refreshes and aged plans.
It estimates the mapping to local monotonic time from the best received offset.
This cannot measure unknown initial transport delay. The station driver must
validate camera/arm clock conventions, synchronization, transport latency and
per-sensor freshness; camera freshness is not inferred from a recent arm sample.

An ordinary exception from SE3 `infer` lets its old action chunk continue.
The bridge therefore converts fatal callback errors into SDK `EndEpisode`,
closes its command queue and requests station episode termination. `None`
means there is no new chunk and preserves the prior chunk. Neither return
value nor `driver.close()` proves a physical stop. Validate the station's
watchdog, disconnect, timeout, home and emergency-stop behavior during
commissioning. The station enforces its episode rollout time even while the
worker is blocked on a model.

## Visibility and evaluation

`Scenario.truth` is evaluator-private. The trusted driver may use it only to
configure independent scoring/reset validation, never to choose actions or
fill public observations with hidden answers. Object IDs must be neutral,
especially for Cover Blocks. Observation masking must remove hidden color,
identity and pose information instead of preserving a stale full-scene map.
Policy memory is reset per episode; evaluator event history is separate.

The evaluator must implement all facts consumed by `scoring.py`. These include
support relations, containment, release/settling, orientation, correct insertion
depth, observed press/uncover order and continuous no-lift evidence for Align
Blocks. Store raw measurements and frozen thresholds so predicates are auditable.
Do not derive successful placements or counts merely from accepted commands.
Home must be measured before station termination; station auto-home after the
episode is not proof the policy satisfied the task.

Required driver acceptance tests: wrong arm/camera/calibration; malformed,
out-of-bounds or colliding trajectories; stale camera with fresh arm state;
occlusion and identity switches; failed grasp; partial insertion; pending,
failed and false-positive verification; duplicate/disconnected packets;
episode reset and cancellation while the model/planner is active. Complete
these in the actual robot simulator and supervised station environment before
adding tasks to `validated_tasks`.
