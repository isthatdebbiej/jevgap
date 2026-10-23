# classify-objects

Sort writing tools, toy vehicle and camera equipment into three bins, one complete category per bin. Any category may use any bin; do not mix categories. Return both arms to origin.

## Reset

Writing tools: black pen and white stylus. Toy vehicle: wooden race car. Camera equipment: action camera and two black mounts. Red, blue and green bins. All six objects begin outside bins. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — 3 complete categories, each in a distinct bin, with every category member inside, no foreign objects and grippers open. All objects settled and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 15: 1 complete categories, each in a distinct bin, with every category member inside, no foreign objects and grippers open.

- 2: 40: 2 complete categories, each in a distinct bin, with every category member inside, no foreign objects and grippers open.

- 3: 100: 3 complete categories, each in a distinct bin, with every category member inside, no foreign objects and grippers open. All objects settled and arms at origin.

**q_0_0** — 0->15, phase 1: Did it identify and acquire every member of category 1? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->15, phase 2: Did it carry all objects of category 1 over the same chosen unused bin? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->15, phase 3: Did it release all category 1 members fully inside, verify completeness and no contamination? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 15->40, phase 1: Did it identify and acquire every member of category 2? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 15->40, phase 2: Did it carry all objects of category 2 over the same chosen unused bin? If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 15->40, phase 3: Did it release all category 2 members fully inside, verify completeness and no contamination? Preserve earlier qualifying units. If milestone 15 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 40->100, phase 1: Did it identify and acquire every member of category 3? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 40->100, phase 2: Did it carry all objects of category 3 over the same chosen unused bin? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 40->100, phase 3: Did it release all category 3 members fully inside, verify completeness and no contamination? Verify all completed units and return both arms to origin. If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
