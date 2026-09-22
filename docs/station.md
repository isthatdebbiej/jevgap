# Evaluation station integration

The station package separates observation access, perception, model execution,
action admission and controller feedback. The first implementations are a fake
station and MuJoCo YAM. Physical dispatch is not implemented.

## Offline commands

After the existing setup script, run from the repository root:

```bash
PY="$HOME/.local/share/rtbench/yam-venv/bin/python"
"$PY" scripts/station.py --config configs/station-fake.json \
  --output "$HOME/.local/share/rtbench/results/station-shadow"
"$PY" scripts/station.py --config configs/station-fake.json --dispatch-sim \
  --output "$HOME/.local/share/rtbench/results/station-dispatch"
"$PY" scripts/station.py --config configs/station-yam.json --dispatch-sim \
  --output "$HOME/.local/share/rtbench/results/station-yam"
```

Output directories must be new. The default is shadow mode: the runner has an
observation port and recorder but no dispatcher. `--dispatch-sim` enables only
simulation controllers. A config naming a hardware station is refused.

Station, executor, provider and perception are independent config selections:

| Field | Supported values |
|---|---|
| station | fake, yam_sim |
| executor | native, rust |
| provider | diagnostic, astra, jev |
| perception | poses, rgbd |

The A/B presets retain native GaP + Astra and GaP + Jev + custom Rust executor.
Both require an explicit `--live` argument and the selected provider's credential
file; existing durable budget caps apply. Offline diagnostic runs make no API calls.
Changing executor or provider does not change the station's command interface.

`poses` consumes station object positions (ground truth in simulation). `rgbd`
uses bounded local image buffers, calibrated camera geometry and the existing
experimental red-cube detector. No image bytes enter model requests or JSON
control records. Missing/evicted images produce missing poses. RGB-D remains a
development path, not reliable hardware perception or a GaP catalog integration.
Calibration and source timestamps remain attached to each observation.

## Interfaces

`python/rtbench/station/contracts.py` defines observations, station capabilities,
commands, feedback and source/controller protocols. Pickup requests, Cartesian
targets and joint trajectories are separate payload types. Both current stations
advertise pickup requests only. Supporting a payload in the type system does not
mean a station can execute it; unsupported commands are rejected, never translated.
The fake command completes after a scripted delay, not a physical grasp. The YAM
command authorizes the existing simulation tracker; its geometry and control
settings are not hardware parameters.

Observations contain station/episode identity, sample and scene versions, capture
clock identity, local receipt time, coordinate frame, robot state and optional
poses/image references. Sources publish while a single workflow is in flight;
only the latest pending observation is kept. The command source must match a
retained observation. At most 256 observations are retained for admission checks.

The local clock token identifies this process's monotonic domain. An adapter
cannot claim a remote camera clock is comparable just because both clocks are
called monotonic. This version refuses unmapped clocks for dispatch. A future
hardware adapter must provide a verified mapping with bounded uncertainty, or
capture locally in the verified domain. Receipt time never substitutes for
capture time when checking freshness.

Admission, scene updates and final dispatch checks share a lock. Accepted commands
remain distinct from running and completed commands. The simulator rechecks
current observation freshness, scene and command expiry while controlling motion.
Stop means holding the simulation's current joint target; it is not an assertion
that physical movement has stopped.

Lost acknowledgements or disconnects produce unknown outcomes and block further
dispatch. Reconnection alone does not clear uncertainty. Only explicit reconciled
terminal feedback clears it; there is no automatic command retry. The fake adapter
offers `reconcile(command_id)` for deterministic tests. A hardware adapter will
need authoritative controller state to implement that operation.

Worker functions receive structured state, not controller handles. This is an
interface boundary, not an OS sandbox for hostile plugins. The current SDK
compatibility imports remain in the checkout's scripts directory; invoke the
provided entrypoint from a checkout rather than treating this as a published wheel.

## Results and fault injection

Every successful runner invocation writes config.json, events.jsonl,
workflows.jsonl, summary.json and report.md. YAM also writes trajectory.jsonl and
its local scene assets. Keep these under ignored results directories: scene assets
can contain machine-specific paths. Public example summaries must exclude those
assets and private inventory values.

Events distinguish proposal, admission, dispatch, acknowledgement, execution
feedback and independent station measurements. Rejected commands and shadow
proposals are never counted as completed. Unreconciled feedback cannot turn an
unknown command into success. The report retains failures, unresolved commands,
observation replacements and timing distributions. Small smoke runs are integration
checks and do not establish a performance advantage or hardware readiness.

Fake-station faults support missing initial observations, delayed capture times,
scene changes, disconnect/reconnect, an unrelated source clock and lost command
acknowledgements. `advance(now)` allows deterministic tests without wall-clock
sleep. Fault settings are not exposed as physical station behavior.

The old moving-cube and continuous runners remain available for reproducing their
published experiments. New station integrations should use this runner; no old
results are reclassified as station-layer measurements.

## Hardware handoff

Complete [the station worksheet](station-worksheet.md) with the evaluation team.
Then implement their observation source and controller adapter, declare actual
capabilities, establish clocks/frames, and run observation-only and shadow checks.
Keep their existing controller and guardrails. Physical dispatch requires a
separate implementation and validation milestone; it cannot be enabled here with
a config switch. Future fleet coordination can address station and task IDs above
this boundary while action admission remains local to each robot.

A generated [offline fake-station example report](examples/station/report.md) and its event log are included. The scripted fake completion is not a YAM pickup result. For combined disconnect and lost-acknowledgement checks, use configs/station-faults.json; for experimental YAM camera input, use configs/station-yam-camera.json.
