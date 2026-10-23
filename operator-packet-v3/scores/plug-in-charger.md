# plug-in-charger

Insert the white USB adapter fully and upright into the marked outlet of the disconnected power strip. Return both arms to origin.

## Reset

White USB wall adapter and disconnected de-energized power strip; mark one outlet, trace allowed strip footprint, route cord clear. Record reference flush seating before rollout. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — Adapter flush in marked outlet, no prong exposure beyond normal reference fit, upright, strip in bounds, gripper released and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 100: Adapter flush in marked outlet, no prong exposure beyond normal reference fit, upright, strip in bounds, gripper released and arms at origin.

**q_0_0** — 0->100, phase 1: Did it grasp and retain adapter without unsafe prong contact? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->100, phase 2: Did it transport to marked outlet and align both prongs for insertion? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->100, phase 3: Did it fully seat and release adapter, leave strip in bounds and return both arms to origin? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
