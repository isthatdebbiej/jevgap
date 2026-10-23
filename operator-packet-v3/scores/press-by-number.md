# press-by-number

Press left green count button nine times, right dark-blue confirm once, middle cyan count button once, then right dark-blue confirm once again. No extra, missing or out-of-order presses. Return both arms to origin.

## Reset

Cards 9 and 1 over left green and middle cyan buttons; right dark-blue confirm. Record each activation with switch signal or clear full press/release video. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — Exact left x9 / confirm / middle x1 / confirm sequence without extra/missed/premature presses, arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 100: Exact left x9 / confirm / middle x1 / confirm sequence without extra/missed/premature presses, arms at origin.

**q_0_0** — 0->100, phase 1: Did it bind card 9 to left, card 1 to middle and plan two confirmations? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->100, phase 2: Did it execute left x9, right confirm, middle x1, right confirm in that order? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->100, phase 3: Were all counts exact without extra/missed/out-of-order presses, then both arms returned to origin? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
