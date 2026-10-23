# insert-tubes

Insert both capped tubes one by one into the two marked wells of the orange rack, upright to the marked depth. Return both arms to origin.

## Reset

Two capped specimen tubes, orange rack with two marked wells and depth witness marks. Begin both tubes outside rack. Trace rack footprint and record fully seated reference. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies. Quality is adapted to 0->50->100; not the three-tube rubric.

## Scoring

**task_success** — Both tubes upright to depth in separate marked wells, rack in footprint and arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 50: One tube upright at marked depth in a marked well, gripper open.

- 2: 100: Both tubes upright to depth in separate marked wells, rack in footprint and arms at origin.

**q_0_0** — 0->50, phase 1: Did it grasp and retain tube 1? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->50, phase 2: Did it carry tube 1 above its unused marked well and align vertically? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->50, phase 3: Did it insert tube 1 to marked depth, release and leave it upright? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 50->100, phase 1: Did it grasp and retain tube 2? If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 50->100, phase 2: Did it carry tube 2 above its unused marked well and align vertically? If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 50->100, phase 3: Did it insert tube 2 to marked depth, release and leave it upright? Verify all completed units and return both arms to origin. If milestone 50 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
