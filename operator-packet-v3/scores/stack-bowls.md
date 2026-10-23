# stack-bowls

Stack three bowls upright and stably. Return both arms to origin.

## Reset

Three nestable bowls. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies. Not in the ten-task Notion proposal. Quality is a declared local adaptation.

## Scoring

**task_success** — All three in one stable stack, released and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 15: Two objects stably stacked, gripper open.

- 2: 100: All three in one stable stack, released and arms at origin.

**q_0_0** — 0->15, phase 1: Did it acquire the next object for stacking step 1? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->15, phase 2: Did it transport and align the retained object above its supporting object? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->15, phase 3: Did it release a stable upright stack without disturbing its support? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 15->100, phase 1: Did it acquire the next object for stacking step 2? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 15->100, phase 2: Did it transport and align the retained object above its supporting object? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 15->100, phase 3: Did it release a stable upright stack without disturbing its support? Verify all completed units and return both arms to origin. If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
