# arrange-largest-number

Arrange the four digit tiles 2, 4, 7, 9 on the four pads from left to right as the largest possible number, upright. Return both arms to origin.

## Reset

Four tiles 2,4,7,9 and four ordered pads. Target 9742; start all tiles off pads; freeze upright yaw reference. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies. Not in the ten-task Notion proposal; four-digit variant fixed. Quality is a declared local adaptation.

## Scoring

**task_success** — 4 tiles in correct descending-order pads and upright, released. All four form 9742 and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 5: 1 tiles in correct descending-order pads and upright, released.

- 2: 15: 2 tiles in correct descending-order pads and upright, released.

- 3: 30: 3 tiles in correct descending-order pads and upright, released.

- 4: 100: 4 tiles in correct descending-order pads and upright, released. All four form 9742 and arms at origin.

**q_0_0** — 0->5, phase 1: Did it select and retain the correct digit for placement 1? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->5, phase 2: Did it transport the digit above its correct pad with upright orientation? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->5, phase 3: Did it release the correct digit on its pad with valid orientation? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 5->15, phase 1: Did it select and retain the correct digit for placement 2? If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 5->15, phase 2: Did it transport the digit above its correct pad with upright orientation? If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 5->15, phase 3: Did it release the correct digit on its pad with valid orientation? Preserve earlier qualifying units. If milestone 5 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 15->30, phase 1: Did it select and retain the correct digit for placement 3? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 15->30, phase 2: Did it transport the digit above its correct pad with upright orientation? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 15->30, phase 3: Did it release the correct digit on its pad with valid orientation? Preserve earlier qualifying units. If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_0** — 30->100, phase 1: Did it select and retain the correct digit for placement 4? If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_1** — 30->100, phase 2: Did it transport the digit above its correct pad with upright orientation? If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_2** — 30->100, phase 3: Did it release the correct digit on its pad with valid orientation? Verify all completed units and return both arms to origin. If milestone 30 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
