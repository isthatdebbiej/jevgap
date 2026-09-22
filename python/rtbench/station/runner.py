"""Station-independent observation, decision and recording loop."""

from dataclasses import asdict, dataclass, replace
import json
import math
import os
from pathlib import Path
import threading
import time

from .adapters import FakeStation, PosesPerception, RGBDPerception, simulation_capabilities
from .boundary import Boundary, ImageBuffer, Recorder, SimulationDispatcher
from .contracts import Command, PickupRequest, Status


@dataclass(frozen=True)
class Config:
    station: str = "fake"
    station_id: str = "sim-1"
    executor: str = "native"
    provider: str = "diagnostic"
    perception: str = "poses"
    duration_s: float = 1.0
    worker_delay_s: float = 0.05
    age_s: float = 5.0
    command_ttl_s: float = 30.0
    decision_interval_s: float = 0.05
    max_calls: int = 50
    faults: dict | None = None

    def __post_init__(self):
        if self.station not in {"fake", "yam_sim"}:
            raise ValueError("Only fake and yam_sim stations are executable; hardware adapters are pending")
        if self.executor not in {"native", "rust"} or self.provider not in {"diagnostic", "astra", "jev"}:
            raise ValueError("Unknown executor/provider")
        if self.perception not in {"poses", "rgbd"} or not self.station_id:
            raise ValueError("Unknown perception source or empty station ID")
        for name in ["duration_s", "age_s", "command_ttl_s", "worker_delay_s", "decision_interval_s"]:
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid timing parameter")
        if (
            min(self.duration_s, self.age_s, self.command_ttl_s) <= 0
            or type(self.max_calls) is not int
            or not 0 < self.max_calls <= 10000
        ):
            raise ValueError("Invalid duration/budget")
        allowed = {
            "disconnect_s",
            "reconnect_s",
            "missing_until_s",
            "scene_change_s",
            "observation_delay_s",
            "source_clock",
            "ack_loss",
        }
        if self.faults is not None and (not isinstance(self.faults, dict) or set(self.faults) - allowed):
            raise ValueError("Unknown fault scenario")
        for key, value in (self.faults or {}).items():
            if key == "ack_loss":
                valid = isinstance(value, bool)
            elif key == "source_clock":
                valid = isinstance(value, str) and bool(value)
            else:
                valid = (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and value >= 0
                )
            if not valid:
                raise ValueError("Invalid fault setting")
        if self.station != "fake" and self.faults:
            raise ValueError("Fault injection is supported by the fake station only")


class ObservationPort:
    """Capability restriction for shadow runners; not protection from hostile code."""

    def __init__(self, station):
        self.capabilities = station.capabilities
        self.start, self.close, self.measurements = station.start, station.close, station.measurements


class Runner:
    def __init__(self, config, source, perception, boundary, runtime, dispatcher=None):
        self.config, self.source, self.perception = config, source, perception
        self.boundary, self.runtime, self.dispatcher = boundary, runtime, dispatcher
        self.workflows = []

    def run(self):
        b, c = self.boundary, self.config
        rec = b.recorder
        begin = time.monotonic_ns()
        deadline = begin + int(c.duration_s * 1e9)
        finished = threading.Event()
        calls = 0
        failures = 0
        next_request_ns = 0

        def publish(observation):
            started = time.monotonic_ns()
            try:
                processed = self.perception.process(observation)
            except Exception as exc:
                rec.emit("perception_failed", sample_id=observation.sample_id, error_type=type(exc).__name__)
                processed = replace(observation, poses={})
            rec.emit(
                "perception",
                sample_id=observation.sample_id,
                start_ns=started,
                end_ns=time.monotonic_ns(),
                valid=bool(processed.poses),
            )
            b.observe(processed)

        def monitor():
            while not finished.is_set():
                if time.monotonic_ns() >= deadline:
                    with b.lock:
                        b.ended = True
                    if self.dispatcher:
                        self.dispatcher.stop()
                    return
                if self.dispatcher:
                    self.dispatcher.poll()
                finished.wait(0.01)

        monitor_thread = threading.Thread(target=monitor)
        try:
            self.source.start(publish)
            monitor_thread.start()
            while time.monotonic_ns() < deadline:
                if time.monotonic_ns() < next_request_ns:
                    finished.wait(0.005)
                    continue
                o = b.take()
                with b.lock:
                    completed = Status.COMPLETED in b.statuses.values()
                    committed = b.commands[b.active].scene_version if b.active and b.active not in b.unknown else -1
                if o is None or completed or calls >= c.max_calls:
                    finished.wait(0.01)
                    continue
                state = dict(
                    observation_id=o.sample_id,
                    scene_version=o.scene_version,
                    captured_ns=o.captured_ns,
                    committed_scene_version=committed,
                    target=o.poses.get("cube"),
                    joint_positions=o.robot_state.get("joint_positions", []),
                    observation_valid="cube" in o.poses and o.connected,
                    task="Pick up the cube using the station's existing controller.",
                    observation="Object pose available." if o.poses else "Object pose missing; reperceive.",
                    current_plan="Current pickup running."
                    if committed == o.scene_version
                    else "A new plan is required.",
                )
                calls += 1
                submitted = time.monotonic_ns()
                try:
                    result = self.runtime.run(state, calls)
                    returned = time.monotonic_ns()
                    next_request_ns = returned + int(c.decision_interval_s * 1e9)
                    self.workflows.append(
                        dict(sample_id=o.sample_id, submitted_ns=submitted, returned_ns=returned, result=result)
                    )
                    outputs = result["outputs"]
                    p = outputs["bench.proposal" if "bench.proposal" in outputs else "proposal"]["proposal"]
                    rec.emit(
                        "decision",
                        sample_id=o.sample_id,
                        submitted_ns=submitted,
                        returned_ns=returned,
                        decision=p["decision"],
                    )
                    if p["decision"] not in {"continue", "replan"}:
                        if self.dispatcher:
                            self.dispatcher.stop_active("policy_" + p["decision"], observation=o)
                        continue
                    if p["decision"] == "continue":
                        rec.emit("retained_plan", sample_id=o.sample_id, active_command=b.active)
                        continue
                    if p["target"] is None:
                        rec.emit("proposal_rejected", reason="missing_pose", sample_id=o.sample_id)
                        continue
                    command = Command(
                        f"{o.station_id}:{o.episode_id}:{calls}",
                        "pickup-1",
                        o.station_id,
                        o.episode_id,
                        p["source_observation_id"],
                        p["source_scene_version"],
                        p["source_captured_ns"],
                        o.source_clock,
                        returned + int(c.command_ttl_s * 1e9),
                        o.frame,
                        PickupRequest("cube", tuple(p["target"])),
                    )
                    if b.admit(command) is None:
                        if self.dispatcher:
                            self.dispatcher.dispatch(command)
                        else:
                            rec.emit("shadow_proposal", command_id=command.command_id, at_ns=time.monotonic_ns())
                except Exception as exc:
                    failures += 1
                    rec.emit("workflow_failed", error_type=type(exc).__name__, at_ns=time.monotonic_ns())
                    break
        except Exception as exc:
            failures += 1
            rec.emit("runner_failed", error_type=type(exc).__name__, at_ns=time.monotonic_ns())
        finally:
            finished.set()
            if monitor_thread.ident:
                monitor_thread.join()
            if self.dispatcher:
                self.dispatcher.stop()
            else:
                with b.lock:
                    b.ended = True
            try:
                self.source.close()
            finally:
                self.runtime.close()
        return dict(
            mode="simulation_dispatch" if self.dispatcher else "shadow",
            provider=c.provider,
            executor=c.executor,
            calls=calls,
            workflow_failures=failures,
            call_limit_reached=calls >= c.max_calls,
            statuses={k: str(v) for k, v in b.statuses.items()},
            unresolved_commands=sorted(b.unknown),
            observation_replacements=b.slot.replaced,
            pending_observations=int(b.slot.pending is not None),
            measurements=self.source.measurements(),
        )


def execute(config, output, dispatch=False, live=False):
    import sys

    legacy = str(Path(__file__).resolve().parents[3] / "scripts")
    if legacy not in sys.path:
        sys.path.insert(0, legacy)
    if config.provider != "diagnostic" and not live:
        raise ValueError("Remote providers require --live")
    if config.provider != "diagnostic":
        name = {"astra": "ASTRA_KEY_FILE", "jev": "JEV_KEY_FILE"}[config.provider]
        path = Path(os.environ.get(name, ""))
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Set {name} to a readable credential file")
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_text(json.dumps(dict(asdict(config), dispatch=dispatch, live=live), indent=2))
    recorder, images = Recorder(), ImageBuffer()
    b = Boundary(simulation_capabilities(config.station_id), recorder, int(config.age_s * 1e9))
    if config.station == "fake":
        station = FakeStation(b, images, config.duration_s, config.faults, config.perception)
    else:
        from .yam import YamStation

        station = YamStation(b, images, output / "simulation", config.duration_s, config.perception)
    from executors import Native, Rust, ROOT

    worker = dict(
        mode="diagnostic" if config.provider == "diagnostic" else "live",
        max_calls=config.max_calls,
        diagnostic_delay_s=config.worker_delay_s,
        entrypoint={"astra": "astra_provider:decide", "jev": "jev_provider:decide"}.get(config.provider),
    )
    perception = PosesPerception() if config.perception == "poses" else RGBDPerception(images)
    runtime = (Native if config.executor == "native" else Rust)(
        ROOT / "workflows/yam_pickup/workflow.json", worker, output
    )
    runner = Runner(
        config, ObservationPort(station), perception, b, runtime, SimulationDispatcher(b, station) if dispatch else None
    )
    summary = runner.run()
    from .report import write_report

    write_report(output, summary, recorder.rows, runner.workflows)
    if hasattr(station, "frames"):
        (output / "trajectory.jsonl").write_text("".join(json.dumps(row) + "\n" for row in station.frames))
    return summary
