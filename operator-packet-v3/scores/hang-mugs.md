# hang-mugs

Hang both mugs by their handles on separate pegs of the wooden mug tree. Return both arms to origin.

## Reset

Two ceramic mugs and upright wooden mug tree. Start mugs on table; base/table support does not count as hanging. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies. Quality uses adapted intervals 0->40->100 with the same 30/30/40 phase rule; not the three-mug rubric.

## Scoring

**task_success** — Both mugs securely hung on separate pegs, rack upright and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 40: One mug securely hung, gripper open and rack upright.

- 2: 100: Both mugs securely hung on separate pegs, rack upright and arms at origin.

**q_0_0** — 0->40, phase 1: Did it grasp and retain mug 1 without tipping or dropping it? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->40, phase 2: Did it carry mug 1 and align its handle with a different free peg? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->40, phase 3: Did it hang and release mug 1, withdraw and leave the rack upright? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 40->100, phase 1: Did it grasp and retain mug 2 without tipping or dropping it? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 40->100, phase 2: Did it carry mug 2 and align its handle with a different free peg? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 40->100, phase 3: Did it hang and release mug 2, withdraw and leave the rack upright? Verify all completed units and return both arms to origin. If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
