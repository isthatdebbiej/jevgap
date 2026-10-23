# Precision Long-Horizon Memory

**Hardware proposal · YAM arm · 12–15 scored episodes**

## Objective

Test whether a robot can remember an earlier instruction, retain it through intervening work, and precisely place the correct cubes—even after an instruction correction or a cube changes position.

The demonstration: **show the job → remove the instruction → complete eight transfers → execute three placements from memory.** All tasks use dry, reusable props with quick resets and no spills or mess.

## Hardware and props

| Item | Requirement |
|---|---|
| Robot | One YAM arm with parallel gripper and the lab’s validated motion limits |
| Cubes | Five active cubes: three task cubes and two distractors; approximately 35–40 mm, subject to gripper fit |
| Labels | Unique cube IDs and directional arrows for orientation scoring |
| Work surface | Fixed matte board with three neutral target marks, three starting positions, and four distractor buffer positions |
| Observation | Fixed overhead camera, calibrated board markers, consistent lighting; side camera preferred for grasp/release verification |
| Instruction cue | Screen or digital event presenting a temporary job card and correction |
| Moving-cube fixture | Indexed sliding carrier with two locked positions; cube remains freely graspable |
| Reset kit | Placement template and storage tray; low outer catch rim outside normal robot paths |

Use flat target marks rather than funnels or tight nests that mechanically correct placement. No liquids, powders, loose beads, food, or consumables. Confirm cube dimensions, target spacing, and reachable layout before fabrication.

## Task design

Each episode contains **11 required pick-and-place transfers**: eight distractor transfers followed by three remembered placements.

Example initial instruction:

> After the transport jobs, place A at T2 facing 90°, then C at T1 facing 0°, then B at T3 facing 180°. Leave A, B, and C untouched until the final execute cue.

Remove the instruction. Move the two distractor cubes between their buffer positions for eight transfers, returning them to their starting positions. Then issue only: **“Execute the remembered job.”**

| Scenario | What changes | What it tests |
|---|---|---|
| 1. Delayed instruction | Initial job disappears before eight intervening transfers | Retention of assignments, order, and orientation |
| 2. Different history, same scene | Different initial job; same final visible scene and distractor sequence as Scenario 1 | Whether earlier information actually determines the final actions |
| 3. Instruction correction | After transfer 2: “Swap A’s and B’s destinations; preserve order and orientation” | Updating remembered information and retaining it through six more transfers |
| 4. Correction + moving cube | Repeat Scenario 3; relocate A after a final-decision observation, before pickup | Remembering the goal while using fresh source geometry |

For Scenario 4, hold the arm clear while the fixture moves, then lock the fixture before pickup. This first pilot uses **move–stop–pick**. Record whether movement overlaps an outstanding decision and whether an outdated command is rejected.

The policy must retain the job itself. Subsequent observations must not repeat the hidden assignment or reveal the correct next placement. Clear episode memory between runs and give every policy the same observation and history access.

## Policy comparison and episode count

Compare:

- **Code as Policies + Astra**
- **Graph as Policy + Astra**
- **Graph as Policy + Jev + Rust**

Run each of the four scenarios once per policy: **4 × 3 = 12 scored episodes**. If time permits, add three control episodes—one per policy—with the current job instruction kept visible, bringing the total to **15**.

Use identical starting layouts, instructions, perception, robot skills, motion limits, and scoring. Rotate policy order between scenarios and reset the scene between runs. Commissioning trials are separate from scored episodes.

## Scoring

**Full success:** all 11 transfers completed in the required sequence; all final cubes at the correct targets and orientations; no early task-cube moves or manual assistance.

Proposed placement thresholds, to confirm against calibration before collection:

- Cube-center error **≤10 mm**.
- Directional yaw error **≤10°**.
- Stable placement for **2 seconds after release**.

Record remembered object/target/orientation choices separately from physical placement errors. Also record completed transfers, total time, stale-command rejection and recovery, drops, retries, and operator interventions.

Use a common **eight-minute episode limit** and at most one retry per verified failed transfer. Keep failures in the results. Report per-scenario outcomes and success counts; 12–15 episodes are a feasibility pilot, not enough to establish a reliable ranking or isolate a Rust benefit.

## Request to the hardware team

1. Confirm the cube size, reachable layout, camera accuracy, and moving-fixture availability.
2. Prepare the clean prop kit and verify reliable static transfers, placement measurement, and stop/interlock behavior.
3. Reserve a **3–4 hour collection slot after commissioning** for 12–15 scored episodes and resets.
4. Capture synchronized video, action outcomes, final placement errors, timing, and interventions for every run.

**Publication deliverable:** a compact benchmark page with task videos, apparatus/reset instructions, scoring rules, and a three-policy results table. Expand later with more matched runs, longer action sequences, and varied layouts.
