# pack-objects-into-box

Place the car, shoe, toothbrush and hammer fully inside the open box, pointing the car nose, shoe toe, toothbrush head and hammer striking face left. Return both arms to origin.

## Reset

Orange toy car, red shoe, blue electric toothbrush, claw hammer, open cardboard box. Trace the initial box footprint and record front-left reference. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — 4 objects fully inside, front-left, settled; box stays within initial footprint and grippers open. All four correct and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 10: 1 objects fully inside, front-left, settled; box stays within initial footprint and grippers open.

- 2: 25: 2 objects fully inside, front-left, settled; box stays within initial footprint and grippers open.

- 3: 50: 3 objects fully inside, front-left, settled; box stays within initial footprint and grippers open.

- 4: 100: 4 objects fully inside, front-left, settled; box stays within initial footprint and grippers open. All four correct and arms at origin.

**q_0_0** — 0->10, phase 1: Did the robot grasp and retain object 1 clear of the table? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->10, phase 2: Did it carry object 1 above the box and establish the defined front-left orientation? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->10, phase 3: Did it release object 1 fully inside and settled, with the box aligned and gripper open? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 10->25, phase 1: Did the robot grasp and retain object 2 clear of the table? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 10->25, phase 2: Did it carry object 2 above the box and establish the defined front-left orientation? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 10->25, phase 3: Did it release object 2 fully inside and settled, with the box aligned and gripper open? Preserve earlier qualifying units. If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 25->50, phase 1: Did the robot grasp and retain object 3 clear of the table? If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 25->50, phase 2: Did it carry object 3 above the box and establish the defined front-left orientation? If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 25->50, phase 3: Did it release object 3 fully inside and settled, with the box aligned and gripper open? Preserve earlier qualifying units. If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_0** — 50->100, phase 1: Did the robot grasp and retain object 4 clear of the table? If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_1** — 50->100, phase 2: Did it carry object 4 above the box and establish the defined front-left orientation? If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_2** — 50->100, phase 3: Did it release object 4 fully inside and settled, with the box aligned and gripper open? Verify all completed units and return both arms to origin. If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
