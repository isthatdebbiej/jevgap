# align-blocks

Without picking up any cube, use the metal ruler to push the three purple cubes into one straight aligned row. Return both arms to origin.

## Reset

Three purple cubes and metal ruler. Fix top/side camera geometry, ruler parking position and initial cube poses. Record calibrated collinearity, yaw and no-lift measurements over the entire trajectory. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — Cube centers collinear within frozen tolerance, faces parallel within yaw tolerance, no-lift limit respected throughout, ruler used, arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 100: Cube centers collinear within frozen tolerance, faces parallel within yaw tolerance, no-lift limit respected throughout, ruler used, arms at origin.

**q_0_0** — 0->100, phase 1: Did it grasp and position the ruler edge for pushing without lifting cubes? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->100, phase 2: Did it push all cubes toward a common line with the ruler while respecting the no-lift limit? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->100, phase 3: Did it meet collinearity/yaw tolerances, withdraw without disturbance and return arms to origin? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
