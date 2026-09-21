# Testing on a physical YAM

**Current status: no hardware action bridge is implemented or tested.** The
included runners are simulation-only. This guide describes the staged path to a
physical A/B experiment; it is not a command to run the simulation controller on
hardware.

## 1. Inventory the borrowed robot

Confirm the exact arm variant, gripper, firmware, host OS, CAN channel, camera,
mounting, working volume and stop procedure with the owner. Preserve their known
working SDK configuration and offsets. Different arms/grippers can require
different settings. Do not replace their configuration with simulator gains.

Record these in a local copy of [the inventory template](../configs/hardware.example.json).
Keep serial numbers, network addresses, credentials and private recordings out of
the public repo. Use native Linux for CAN access and measured runs.

## 2. Prove the software path without hardware

Run the README setup and checks. Then run the deterministic moving-cube episode
and inspect its contact and completion logs. For the manufacturer's interactive
viewer, `bash scripts/view-yam.sh` explicitly passes `--sim`; this matters because
the pinned SDK's viewer defaults to a physical connection when the flag is omitted.

## 3. Manufacturer bring-up, with the owner

Use the owner's working environment first. For an isolated SDK environment, the
pinned checkout includes its own dependency lock:

```bash
cd vendor/i2rt
UV_PROJECT_ENVIRONMENT="$HOME/.local/share/rtbench/hardware-venv" uv sync --frozen
```

This installs the **full SDK**, separate from the lightweight benchmark environment.
It may require additional native build dependencies. It is not part of CI.

Follow the [official YAM setup](https://doc.i2rt.com/products/yam) for mounting,
power, CAN wiring and calibration. Inspect the existing interface before changing
it. If the owner has not configured CAN, the manufacturer's documented rate is
1 Mbit/s; confirm it matches the installed setup before bringing the link up.

The pinned SDK's manual gravity-compensation entrypoint is:

```bash
# From vendor/i2rt, after the owner has verified CAN, model and gripper:
"$HOME/.local/share/rtbench/hardware-venv/bin/python" \
  i2rt/robots/motor_chain_robot.py \
  --arm yam --gripper linear_4310 --channel can0 --operation-mode gravity_comp
```

This **connects to and energizes hardware**; it is not a read-only check. Replace
the variant/gripper/channel with the verified inventory. Initialization may move
the gripper during calibration. Keep its travel clear, support the arm as required
by the owner, retain the configured motor timeout, and verify the owner's physical
stop/disconnect procedure. Ctrl+C exits the SDK loop; it is not a substitute for
a physical stop. Do not run the SDK's gripper-cycling example as a first check: it
also commands arm positions. Do not command an all-zero pose as a generic home.

Pinned source references:
[factory](https://github.com/i2rt-robotics/i2rt/blob/120c3c81400171174604e503943f8d1ebc891058/i2rt/robots/get_robot.py),
[CLI](https://github.com/i2rt-robotics/i2rt/blob/120c3c81400171174604e503943f8d1ebc891058/i2rt/robots/motor_chain_robot.py).
Upstream source and the actual installed robot take precedence over generic examples.

## 4. Implement the missing hardware boundary

Before executing A/B proposals, implement and test these components:

| Component | Required behavior |
|---|---|
| Observation source | Live camera/robot samples with timestamps and observation IDs; inference must not stop sampling. |
| Calibration | Camera intrinsics, camera-to-base transform, tool/grasp frame, joint offsets and gripper convention verified against measured points. |
| Scene detector | A shared definition of relevant change; scene versions independent of camera sample IDs. |
| Admission gate | Atomically check scene, observation identity/age, bounds and approved action type; recheck queued commands before dispatch. |
| Controller bridge | One shared, bounded trajectory controller for A and B; preserve SDK gains, timeout and gripper force limits. Models never own actuator handles. |
| Watchdog | Verified hold/stop behavior on stale camera state, communication loss, runtime failure, timeouts and operator stop. |
| Success detector | Independent pickup/retention measurement using observations, not model claims. |

Do not port `qfrc_applied`, simulator inverse kinematics, contact-pad dimensions,
friction coefficients or simulated gripper coordinates as hardware settings.
The SDK uses six arm joints plus its own gripper command convention; verify that
mapping on the actual gripper. Do not assume compute cancellation stops motion.

## 5. Shadow mode before motion

Run both graphs against live observations with **dispatch disabled**. Log proposed
actions, source observations, scene versions and admission decisions. Test camera
loss, changed scene, stale/future timestamps, invalid outputs and runtime failure.
Do not infer model quality from latency; validate the shared decision contract on
representative labeled states. Keep camera monitoring active throughout.

## 6. Small supervised trials

First validate the owner's controller independently, without any model in control:
stationary target, limited working region and owner-approved speed/force settings.
Then admit one proposal at a time for a static object. Introduce target motion only
after static pickup and stop behavior are repeatable; keep people outside the
working volume and use a controlled target platform.

Use identical controller, perception, gate and guardrails for A and B. Randomize
matched trial order and record every attempt, including failed pickups, model
timeouts, rejected proposals and operator aborts. Measure observation-to-admission,
detected-change-to-fresh-dispatch, confirmed pickup and retention separately.
Record clock synchronization uncertainty if camera and robot use different clocks.

Publish simulation and physical results separately. The simulation numbers in this
repo are a reason to test the system, not evidence that hardware behavior is safe
or that the same latency difference will transfer.
