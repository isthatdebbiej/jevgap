# SE3 task readiness audit — 2026-10-23

**Status: not ready for a scored GaP/CaP robot comparison.**
The existing 13-task suite and the separate precision/memory proposal are not
interchangeable. The task marked A with an arrow belongs to the latter, as
confirmed by the user. Neither a prop label nor a completed straight-line job
establishes readiness for manipulation.

## Confirmed evidence

- The recorded straight-line job on yam-2 completed and was operator-scored
  successful. A subsequent cached status response is not a fresh connectivity
  or manipulation test.
- A bounded, real CostPlusIQ request to `Qwen/Qwen3.8-27B` returned `READY`,
  `finish_reason=stop`, and usage of 17 input / 2 output tokens. This proves
  authentication and text inference, not vision, grasping or task performance.
- 89 offline tests passed in the actual benchmark checkout after the corrections
  below (the broader staging suite also passed 109 tests earlier). They include native
  GaP execution with diagnostic drivers and synthetic evidence; they are not
  successful hardware episodes or an end-to-end native CaP deployment.
- The user-selected destination is `se3-labs-yam-2` at
  `100.107.161.92:7443`; active station profiles now match it. Previous station
  files were backed up. Astra profiles remain available.
- An Ubuntu workspace environment now imports the real GaP executor, CaP-X
  trial loop and SE3 XPolicyLab API. Its package versions are recorded in
  `requirements-native-linux.lock.txt` in the workspace. CaP-X required an
  opt-in `CAPX_EXTERNAL_ENV_ONLY=1` adaptation to skip unrelated Franka/simulator
  registrations. `cap-x-external-env.patch` records those three initializer
  changes. Trial/model algorithms were not replaced. This adaptation is not
  yet a committed/pinned revision, so upstream preflight must still block it.
- The real native CaP-X trial loop completed a diagnostic code block through
  the shared transport with a canned HTTP response. It correctly reported
  execution success separately from `task_completed=false`. This was not a
  model-generated robot policy or a successful task trial.

## Corrections made

1. Physical CaP trials disable automatic retry. The native trial used to re-arm
   a hardcoded 1,000-second timer after reset. The worker now prevents extending
   its first armed deadline. This worker deadline includes setup time; SE3's
   `Task_Spec.max_rollout_time` separately controls time from first inference.
2. Existing GaP open-model and CaP profiles use 450 seconds per episode.
3. The native CaP worker now accepts an optional `model_config_file` in its
   upstream profile. That file uses the same CostPlusIQ schema as GaP, including
   key-file access, model ID, reasoning setting, token limits and persistent
   reservations. Scoped transport hooks preserve the native code-generation
   loop, register the selected supported vision model and remove HTTP retries.
   Existing profiles have not yet been bound to this new option.
4. A precision/memory protocol now delivers the initial assignment once,
   advances only after independently verified distractor transfers, hides the
   assignment from the static SDK instruction, and supports a one-time
   correction after transfer two. Its SDK scoring sheet uses 450 seconds.
5. A machine-readable audit covers all 13 local tasks plus precision/memory.
   It includes current source hashes so it cannot be mistaken for evidence
   about a later implementation.

## Shared execution gaps

| Layer | What exists | What remains |
|---|---|---|
| XPolicyLab | A callable `evaluate()` wrapper and offline boundary tests | Actual native GaP and CaP deployment functions wired into it; the existing CLI still uses its older paths |
| Robot control | SDK joint/gripper interface and SDK Cartesian/IK examples | A shared deployable control layer that consumes real observations, bounds motion, handles failures and checks effects |
| Model input | CostPlusIQ text/structured-action adapter | Shared live camera/state input; tested image format, context size, latency and stale-decision handling |
| Native GaP | Supplied semantic-action graphs execute in tests | Grounding to real controls; the supplied graphs are not agent-generated graph synthesis/repair |
| Native CaP-X | Checkout, worker and verified Linux imports | Freeze adapted revision; actual SE3 environment binding; matched model settings, limits and output contracts |
| Memory | Bounded explicit memory in the old semantic runner; new cue schedule | Cue/transfer integration in both live policies; matched history access; fresh memory per episode |
| Evidence | Independent scoring contracts and operator scoring | Real geometry/contact/containment measurements, time synchronization and recordings |
| Budgets | Reservation ledger support | Active study budget/reservations remain zero; CaP model configuration is still upstream-owned and unset |
| Failure handling | Unit tests for stale observations, failed effects, timeouts and result disagreement | Hardware commissioning of disconnect, stop, reset, late model response and partial-motion cases |

Additional compatibility problems were found during source inspection:

- CaP-X's visual-feedback model allowlist does not contain the requested
  `Qwen/Qwen3.8-27B` identifier. Simply setting that model name does not establish
  that camera images reach the model. Its generic request branch also does not
  include the GaP adapter's reasoning setting, and its transient-error retry
  loop can outlast the trial unless stopped by the surrounding deadline.
  The new optional shared transport addresses these three problems when enabled;
  real image delivery from a deployed environment still requires testing.
- The linked proposal reports both milestone progress and phase-quality scores.
  The local thirteen-task scorer implements milestone scoring, not the full
  acquire/transport/place quality breakdown. Those are different metrics.

Model reasoning should choose objects, actions and recovery. The shared control
layer should not contain benchmark answers or solve the task for the model.
It still must implement real motion primitives and truthful observations.
An AI-issued command is not evidence that a grasp or placement succeeded.

## Task-specific gaps

All rows also inherit the shared gaps above.

| Task | Required reconciliation or evidence |
|---|---|
| Stack Blocks | Separate rubric from linked ten-task proposal; support topology, release and stability |
| Stack Bowls | Separate rubric; actual nesting and upright/stable placement |
| Arrange Largest Number | Separate rubric; readable digit inventory, row order and placement |
| Pack Objects Into Box | Operational front of car/shoe/toothbrush/hammer; complete settled containment |
| Hang Mugs | Local contract has three mugs; physical proposal has two; normalize milestones and verify hanging |
| Cover Blocks | Physical green/light-blue/dark-blue differs from local red/green/blue; fix recall order and occlusion protocol |
| Press By Number | Physical button roles and counts; settle confirmation protocol; count measured presses, not commands |
| Plug In Charger | Disconnected/de-energized strip, marked socket, insertion criteria and contact limits |
| Insert Tubes | Local three-tube contract versus two physical tubes; marked wells and insertion-depth evidence |
| Classify Objects | Freeze physical inventory/taxonomy and target bins; verify containment |
| Play Stacking Toy | Local four pegs/ten pieces versus physical five pegs/fifteen pieces; update rubric and depths |
| Align Blocks | Ruler versus set square; freeze alignment tolerance; verify pushing without lifting |
| Classify Objects By Language | Freeze prompt mapping, bins, inventory and held-out assignments |
| Precision/Memory | Five cubes, board/targets, yaw reference, 11 verified transfers, hidden cue integration and independent placement measurement |

The precision proposal's 10 mm / 10 degree thresholds are proposals to confirm
against measurement accuracy. The same-scene alternate-history and moving-cube
variants still need executable schedules and scoring. The current thirteen-task
action schema cannot represent numeric yaw targets. A single labelled cube is
not enough to perform the full eleven-transfer protocol.

## Acceptance before saying “runnable”

Each task needs a resolved physical task definition, identical observations and
basic controls for GaP/CaP, a real model round trip, a native deployment through
XPolicyLab, station-enforced 450-second timing, an operator-confirmed reset,
independent retained results, and a supervised commissioning episode. Failures
must remain in the record. The old straight-line result, import checks, wrappers,
mock tests and configuration flags cannot substitute for these conditions.

The integration code remains our implementation responsibility. Station-specific
start poses, actual layouts, contact/workspace limits and measurement calibration
must come from measured station facts; they cannot be fabricated in configuration.
