# classify-objects-by-language

Put all toy peppers into the left blue bin, all figurines into the middle red bin, and all watches into the right yellow bin. Return both arms to origin.

## Reset

Three toy peppers (red/green/yellow), two figurines, three watches (red-band/yellow-band/black-band); left blue, middle red, right yellow bins. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies.

## Scoring

**task_success** — 3 complete categories, each in its instructed bin, with every category member inside, no foreign objects and grippers open. All objects settled and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 10: 1 complete categories, each in its instructed bin, with every category member inside, no foreign objects and grippers open.

- 2: 40: 2 complete categories, each in its instructed bin, with every category member inside, no foreign objects and grippers open.

- 3: 100: 3 complete categories, each in its instructed bin, with every category member inside, no foreign objects and grippers open. All objects settled and arms at origin.

**q_0_0** — 0->10, phase 1: Did it identify and acquire every member of category 1 using the instructed mapping? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->10, phase 2: Did it carry all objects of category 1 over the instructed bin? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->10, phase 3: Did it release all category 1 members fully inside, verify completeness and no contamination? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 10->40, phase 1: Did it identify and acquire every member of category 2 using the instructed mapping? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 10->40, phase 2: Did it carry all objects of category 2 over the instructed bin? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 10->40, phase 3: Did it release all category 2 members fully inside, verify completeness and no contamination? Preserve earlier qualifying units. If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 40->100, phase 1: Did it identify and acquire every member of category 3 using the instructed mapping? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 40->100, phase 2: Did it carry all objects of category 3 over the instructed bin? If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 40->100, phase 3: Did it release all category 3 members fully inside, verify completeness and no contamination? Verify all completed units and return both arms to origin. If milestone 40 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
