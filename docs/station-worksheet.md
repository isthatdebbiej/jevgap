# Hardware station worksheet

Fill this out privately with the evaluation team. Unknown entries remain unknown;
simulation defaults are not recommended hardware limits.

| Area | Information needed | Integration change |
|---|---|---|
| Station | YAM variant, gripper, SDK/firmware versions, operating system | Adapter environment and capability declaration |
| Observations | API/protocol, sample formats, rates, ordering and reconnect behavior | Observation source `start(publish)` and `close()` |
| Cameras | RGB/depth access, resolution, intrinsics, mounting and calibration format | Image buffer producer and perception adapter |
| Existing perception | Object poses, coordinate frame, confidence and tracking IDs | Consume poses directly where available |
| Clocks | Capture timestamp domain, transport delay and clock synchronization/error bounds | Verified capture-to-local clock mapping |
| Geometry | Robot-base, camera, tool and grasp transforms; verification procedure | Frame validation and calibration configuration |
| Commands | Supported pickup API, Cartesian targets or joint trajectories; units and conventions | Controller `dispatch(command)`; advertise only verified command types |
| Feedback | Accepted/running/completed/error events, command IDs, joint/gripper state | `poll()` and execution-event mapping |
| Reconciliation | How to query a command after an acknowledgement is lost | Authoritative reconciled outcome; no blind retries |
| Limits | Owner-approved workspace, speed, acceleration, torque/gripper limits | Hardware-specific validation supplied by the team |
| Stop | Hold/stop APIs, acknowledgements, watchdogs, physical stop procedure | `stop(command_id)` and verified interruption behavior |
| Evaluation | Pickup/lift/retention definition, available video and gripper evidence | Independent `measurements()` success detector |
| Target movement | Platform/fixture, allowed motion and timing | Matched conditions and scene-change detector |
| Compute | CPU/GPU, process/container permissions, memory budget | Worker/resource configuration |
| Network | Remote model API access, allowed data, local policy serving endpoints | Provider configuration and data-handling agreement |
| Scheduling | Trial window, operator availability, starting number of pairs | Trial manifest and randomized collection order |

Begin with observation-only, then shadow mode, then a static pickup using the
team's controller. Moving-target trials follow reliable static pickup and verified
stop behavior. Serial numbers, credentials, internal endpoints and recordings do
not belong in the public repository.
