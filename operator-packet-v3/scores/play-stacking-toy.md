# play-stacking-toy

Place every piece onto its matching peg: purple circle, blue triangle, green square, orange square and red square. Complete all five groups. Return both arms to origin.

## Reset

Five-peg toy with 15 pieces: 1 purple circle, 2 blue triangles, 3 green squares, 4 orange squares, 5 red squares. Remove every piece before rollout and scatter without hiding peg base. Record matched initial layout and neutral poses for both arms. Confirm ACT start pose, all three camera views, open empty grippers and station stop control. Reset to the identical scene between policies. Quality expands to five intervals 0/10/25/45/70/100, each 30/30/40; not the four-group original.

## Scoring

**task_success** — 5 entire matching peg groups completed, all pieces seated on base/stack and released. All five complete, arms at origin. Every qualifying object must be released, settled for 2 seconds and unsupported by a gripper. Full success also requires both arms at the recorded origin. Judge final state independently of the furthest milestone.

**general_progress** — Furthest cumulative milestone reached during the rollout (review trajectory).

- 0: 0: No qualifying milestone reached.

- 1: 10: 1 entire matching peg groups completed, all pieces seated on base/stack and released.

- 2: 25: 2 entire matching peg groups completed, all pieces seated on base/stack and released.

- 3: 45: 3 entire matching peg groups completed, all pieces seated on base/stack and released.

- 4: 70: 4 entire matching peg groups completed, all pieces seated on base/stack and released.

- 5: 100: 5 entire matching peg groups completed, all pieces seated on base/stack and released. All five complete, arms at origin.

**q_0_0** — 0->10, phase 1: Did it identify and retain every piece of scored group 1? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_1** — 0->10, phase 2: Did it transport each piece of group 1 above the correct peg and align its hole? If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_0_2** — 0->10, phase 3: Did it seat and release every piece to complete group 1? Preserve earlier qualifying units. If milestone 0 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_0** — 10->25, phase 1: Did it identify and retain every piece of scored group 2? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_1** — 10->25, phase 2: Did it transport each piece of group 2 above the correct peg and align its hole? If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_1_2** — 10->25, phase 3: Did it seat and release every piece to complete group 2? Preserve earlier qualifying units. If milestone 10 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_0** — 25->45, phase 1: Did it identify and retain every piece of scored group 3? If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_1** — 25->45, phase 2: Did it transport each piece of group 3 above the correct peg and align its hole? If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_2_2** — 25->45, phase 3: Did it seat and release every piece to complete group 3? Preserve earlier qualifying units. If milestone 25 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_0** — 45->70, phase 1: Did it identify and retain every piece of scored group 4? If milestone 45 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_1** — 45->70, phase 2: Did it transport each piece of group 4 above the correct peg and align its hole? If milestone 45 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_3_2** — 45->70, phase 3: Did it seat and release every piece to complete group 4? Preserve earlier qualifying units. If milestone 45 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_4_0** — 70->100, phase 1: Did it identify and retain every piece of scored group 5? If milestone 70 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_4_1** — 70->100, phase 2: Did it transport each piece of group 5 above the correct peg and align its hole? If milestone 70 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.

**q_4_2** — 70->100, phase 3: Did it seat and release every piece to complete group 5? Verify all completed units and return both arms to origin. If milestone 70 was never reached, select Failure. Grade the whole phase, including retries.

- 0: Failure: no valid progress, wrong target/sequence or unrecovered error.

- 1: Partial: purposeful progress, incomplete/unstable or completed after retry/correction.

- 2: Success: clean stable completion without avoidable retry, recovery or error.
