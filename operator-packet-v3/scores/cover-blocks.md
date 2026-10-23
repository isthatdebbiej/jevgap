# cover-blocks

Cover all three blocks from left to right and remember their colors. Then uncover green, light blue and dark blue in that order, keeping the cups upright. Return both arms to origin.

## Reset

Green, light-blue, dark-blue blocks; three identical yellow opaque cups. Balance all six block-position permutations across matched pairs; record color positions before covering without exposing that record to policy. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — Valid covering followed by green/light-blue/dark-blue reveal order, upright cups, arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 5: All three blocks hidden by upright cups, covered in left-to-right order.

- 2: 15: After valid covering, green uncovered first; both blue blocks remain covered.

- 3: 30: Green then light blue uncovered; dark blue remains covered.

- 4: 100: Valid covering followed by green/light-blue/dark-blue reveal order, upright cups, arms at origin.

**q_0_0** — 0->5, phase 1: Did it acquire the cups in left-to-right action order without disturbing blocks? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->5, phase 2: Did it transport each cup over its corresponding block? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->5, phase 3: Did it hide all blocks under upright cups while retaining their color positions? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 5->15, phase 1: Did it select the cup hiding green from memory? If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 5->15, phase 2: Did it lift and park that cup upright without exposing a later target? If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 5->15, phase 3: Did it reveal green in the required order while preserving remaining covers? If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 15->30, phase 1: Did it select the cup hiding light blue from memory? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 15->30, phase 2: Did it lift and park that cup upright without exposing a later target? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 15->30, phase 3: Did it reveal light blue in the required order while preserving remaining covers? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_0** — 30->100, phase 1: Did it select the cup hiding dark blue from memory? If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_1** — 30->100, phase 2: Did it lift and park that cup upright without exposing a later target? If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_2** — 30->100, phase 3: Did it reveal dark blue in the required order while preserving remaining covers? Verify full order and return arms to origin. If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
