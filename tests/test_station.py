from dataclasses import replace
import threading
import time
from types import SimpleNamespace
import numpy as np
import pytest

from rtbench.station.adapters import FakeStation, PosesPerception, RGBDPerception, simulation_capabilities
from rtbench.station.boundary import Boundary, Recorder, SimulationDispatcher, ImageBuffer
from rtbench.station.contracts import (
    Command,
    CommandType,
    CartesianTarget,
    JointTrajectory,
    PickupRequest,
    ExecutionEvent,
    Status,
    Observation,
    LOCAL_CLOCK,
    action_valid,
)
from rtbench.station.runner import Config, Runner, ObservationPort


@pytest.fixture
def rig():
    clock = [1_000_000_000]
    b = Boundary(simulation_capabilities("s"), Recorder(), age_ns=1000, clock=lambda: clock[0])
    o = Observation("s", "e", 1, 0, clock[0], clock[0], LOCAL_CLOCK, "robot_base", {}, {"cube": (0.2, 0, 0.1)})
    b.observe(o)
    c = Command(
        "c",
        "task",
        "s",
        "e",
        1,
        0,
        clock[0],
        LOCAL_CLOCK,
        clock[0] + 2000,
        "robot_base",
        PickupRequest("cube", (0.2, 0, 0.1)),
    )
    fake = FakeStation(b, ImageBuffer(), clock=lambda: clock[0])
    return clock, b, o, c, fake, SimulationDispatcher(b, fake)


def test_scene_change_between_admission_and_dispatch(rig):
    clock, b, o, c, station, dispatch = rig
    assert b.admit(c) is None
    b.observe(replace(o, sample_id=2, scene_version=1))
    assert dispatch.dispatch(c) == "stale_scene"
    assert station.dispatch_calls == 0
    assert b.statuses["c"] == Status.REJECTED


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"scene_version": 1}, "future_scene"),
        ({"source_clock": "remote-clock"}, "unmapped_clock"),
        ({"expires_ns": 0}, "expired_command"),
        ({"sample_id": 10}, "unknown_observation"),
        ({"frame": "camera"}, "coordinate_frame"),
        ({"action": CartesianTarget((0, 0, 0), (0, 0, 0, 1))}, "unsupported_command"),
        ({"action": PickupRequest("cube", (float("nan"), 0, 0))}, "invalid_action"),
    ],
)
def test_invalid_commands_never_dispatch(rig, change, reason):
    _, b, _, c, station, dispatch = rig
    bad = replace(c, **change)
    assert b.admit(bad) == reason
    dispatch.dispatch(bad)
    assert station.dispatch_calls == 0


def test_expiry_receipt_time_does_not_hide_capture_age(rig):
    clock, b, o, c, _, _ = rig
    clock[0] += 1001
    b.observe(replace(o, sample_id=2, received_ns=clock[0]))
    assert b.admit(c) == "stale_current_observation"


def test_late_response_after_episode_end(rig):
    _, b, _, c, station, d = rig
    b.ended = True
    assert b.admit(c) == "episode_ended"
    d.dispatch(c)
    assert station.dispatch_calls == 0


def test_duplicate_id_does_not_dispatch_twice(rig):
    _, b, _, c, station, d = rig
    assert b.admit(c) is None
    d.dispatch(c)
    assert b.admit(c) == "duplicate_command"
    d.dispatch(c)
    assert station.dispatch_calls == 1
    assert b.statuses["c"] == Status.ACCEPTED


def test_lost_ack_blocks_until_explicit_reconciliation(rig):
    clock, b, o, c, station, d = rig
    station.faults["ack_loss"] = True
    b.admit(c)
    d.dispatch(c)
    assert b.statuses["c"] == Status.UNKNOWN
    b.event(ExecutionEvent("c", Status.COMPLETED, clock[0]))
    assert b.statuses["c"] == Status.UNKNOWN
    assert b.admit(replace(c, command_id="other")) == "unreconciled_command"
    station.executed.add("c")
    b.event(station.reconcile("c"))
    assert not b.unknown
    assert b.statuses["c"] == Status.COMPLETED
    assert station.dispatch_calls == 1


def test_disconnect_then_reconnect_does_not_imply_stopped(rig):
    clock, b, o, c, station, d = rig
    b.admit(c)
    d.dispatch(c)
    b.observe(replace(o, sample_id=2, connected=False))
    b.observe(replace(o, sample_id=3, connected=True))
    assert b.statuses["c"] == Status.UNKNOWN
    assert b.admit(replace(c, command_id="other")) == "unreconciled_command"
    b.event(station.reconcile("c"))
    assert b.statuses["c"] == Status.INTERRUPTED


def test_rejected_command_cannot_become_completed(rig):
    clock, b, _, c, _, _ = rig
    b.admit(replace(c, expires_ns=0))
    b.event(ExecutionEvent("c", Status.COMPLETED, clock[0], reconciled=True))
    assert b.statuses["c"] == Status.REJECTED
    b.event(ExecutionEvent("unknown", Status.COMPLETED, clock[0]))
    assert "unknown" not in b.statuses


def test_atomic_scene_update_and_dispatch(rig):
    _, b, o, c, station, d = rig
    b.admit(c)
    started = threading.Event()

    def update():
        started.set()
        b.observe(replace(o, sample_id=2, scene_version=1))

    with b.lock:
        worker = threading.Thread(target=update)
        worker.start()
        started.wait()
        d.dispatch(c)
    worker.join()
    d.poll()
    assert station.dispatch_calls == 1
    assert b.statuses["c"] == Status.INTERRUPTED


def test_bounded_image_refs_and_rgbd():
    buffer = ImageBuffer(64)
    first = buffer.put(np.zeros((8, 8), dtype=np.uint8))
    buffer.put(np.ones((8, 8), dtype=np.uint8))
    with pytest.raises(KeyError):
        buffer.get(first)
    with pytest.raises(ValueError):
        buffer.put(np.ones((9, 9)))
    b = Boundary(simulation_capabilities("s"), Recorder())
    images = ImageBuffer()
    fake = FakeStation(b, images, perception="rgbd")
    fake.publish = lambda o: b.observe(RGBDPerception(images).process(o))
    fake.advance(fake.clock())
    assert np.allclose(b.latest.poses["cube"], [0.25, -0.035, 0.139])
    assert b.latest.images and not any(isinstance(x, np.ndarray) for x in b.latest.images.values())


class DiagnosticRuntime:
    def run(self, state, execution_id):
        time.sleep(0.02)
        return {
            "outputs": {
                "proposal": {
                    "proposal": dict(
                        source_observation_id=state["observation_id"],
                        source_scene_version=state["scene_version"],
                        source_captured_ns=state["captured_ns"],
                        target=state["target"],
                        decision="replan",
                    )
                }
            }
        }

    def close(self):
        pass


def test_shadow_cannot_dispatch_even_valid_proposal():
    config = Config(duration_s=0.12)
    b = Boundary(simulation_capabilities("s"), Recorder())
    station = FakeStation(b, ImageBuffer(), duration_s=0.12)
    port = ObservationPort(station)
    assert not hasattr(port, "dispatch")
    result = Runner(config, port, PosesPerception(), b, DiagnosticRuntime()).run()
    assert any(e["kind"] == "shadow_proposal" for e in b.recorder.rows)
    assert station.dispatch_calls == 0
    assert Status.COMPLETED not in b.statuses.values()


def test_missing_observations_do_not_invoke_policy():
    b = Boundary(simulation_capabilities("s"), Recorder())
    station = FakeStation(b, ImageBuffer(), duration_s=0.05, faults={"missing_until_s": 1})
    result = Runner(Config(duration_s=0.05), ObservationPort(station), PosesPerception(), b, DiagnosticRuntime()).run()
    assert result["calls"] == 0


def test_physical_configs_and_dispatch_refused(rig):
    with pytest.raises(ValueError):
        Config(station="hardware")
    _, b, _, _, station, _ = rig
    b.capabilities = replace(b.capabilities, simulation=False)
    with pytest.raises(ValueError):
        SimulationDispatcher(b, station)


def test_joint_and_cartesian_contracts_remain_distinct():
    assert action_valid(JointTrajectory(("j1",), ((0.0,), (0.1,)), (0.0, 1.0)))
    assert not action_valid(JointTrajectory(("j1",), ((0.0,), (0.1,)), (1.0, 0.0)))
    assert not action_valid(CartesianTarget((0, 0, 0), (0, 0, 0, 0)))


def test_native_and_rust_identical_station_inputs(tmp_path):
    from executors import Native, Rust, ROOT
    from pathlib import Path
    import os

    if not Path(
        os.environ.get("RTBENCH_BINARY", str(Path.home() / ".cache/rtbench/target/release/rtbench-runtime"))
    ).is_file():
        pytest.skip("Build the Rust runtime before the integration test")
    outputs = []
    for runtime_type in [Native, Rust]:
        folder = tmp_path / runtime_type.__name__
        folder.mkdir()
        runtime = runtime_type(ROOT / "workflows/yam_pickup/workflow.json", {"mode": "diagnostic"}, folder)
        try:
            state = dict(
                observation_id=1, scene_version=0, captured_ns=100, committed_scene_version=-1, target=[0.2, 0, 0.1]
            )
            result = runtime.run(state, 1)
            p = result["outputs"]["bench.proposal" if runtime_type == Native else "proposal"]["proposal"]
            outputs.append({k: v for k, v in p.items() if k not in {"request_start_ns", "decision_ready_ns"}})
        finally:
            runtime.close()
    assert outputs[0] == outputs[1]
    admissions = []
    for proposal in outputs:
        b = Boundary(simulation_capabilities("s"), Recorder(), age_ns=1000, clock=lambda: 101)
        b.observe(Observation("s", "e", 1, 0, 100, 101, LOCAL_CLOCK, "robot_base", {}, {"cube": (0.2, 0, 0.1)}))
        admissions.append(
            b.admit(
                Command(
                    "c",
                    "task",
                    "s",
                    "e",
                    proposal["source_observation_id"],
                    proposal["source_scene_version"],
                    proposal["source_captured_ns"],
                    LOCAL_CLOCK,
                    10000,
                    "robot_base",
                    PickupRequest("cube", tuple(proposal["target"])),
                )
            )
        )
    assert admissions == [None, None]


def test_worker_failure_is_recorded_and_closed():
    class FailedRuntime:
        closed = False

        def run(self, state, execution_id):
            raise TimeoutError()

        def close(self):
            self.closed = True

    b = Boundary(simulation_capabilities("s"), Recorder())
    station = FakeStation(b, ImageBuffer(), duration_s=0.1)
    runtime = FailedRuntime()
    result = Runner(Config(duration_s=0.1), ObservationPort(station), PosesPerception(), b, runtime).run()
    assert result["workflow_failures"] == 1
    assert runtime.closed
    assert station.dispatch_calls == 0


def test_remote_providers_require_explicit_live_flag(tmp_path):
    from rtbench.station.runner import execute

    for provider in ["astra", "jev"]:
        with pytest.raises(ValueError, match="--live"):
            execute(Config(provider=provider), tmp_path / provider)
        assert not (tmp_path / provider).exists()


def test_adapter_rejects_unknown_object(rig):
    _, b, _, c, station, d = rig
    c = replace(c, action=PickupRequest("unknown-object", (0.2, 0, 0.1)))
    assert b.admit(c) is None
    d.dispatch(c)
    assert b.statuses["c"] == Status.REJECTED
    assert not station.executed


def test_config_backend_and_source_are_independent():
    from itertools import product

    for executor, provider, source in product(["native", "rust"], ["diagnostic", "astra", "jev"], ["poses", "rgbd"]):
        assert Config(executor=executor, provider=provider, perception=source).provider == provider
    with pytest.raises(ValueError):
        Config(faults={"disconnect_s": "never"})


def test_changed_admitted_command_never_dispatches(rig):
    _, b, _, c, station, d = rig
    b.admit(c)
    changed = replace(c, action=PickupRequest("cube", (0.4, 0, 0.1)))
    assert d.dispatch(changed) == "command_changed"
    assert station.dispatch_calls == 0
    assert b.statuses[c.command_id] == Status.REJECTED


def test_admission_snapshots_mutable_payload(rig):
    _, b, _, c, station, d = rig
    position = [0.2, 0, 0.1]
    c = replace(c, action=PickupRequest("cube", position))
    b.admit(c)
    position[0] = 0.4
    assert d.dispatch(c) == "command_changed"
    assert station.dispatch_calls == 0


@pytest.mark.parametrize("expiry", [float("nan"), float("inf"), "forever", True])
def test_invalid_expiry_fails_closed(rig, expiry):
    _, b, _, c, station, d = rig
    c = replace(c, expires_ns=expiry)
    assert b.admit(c) == "invalid_command_metadata"
    d.dispatch(c)
    assert station.dispatch_calls == 0


@pytest.mark.parametrize("wrong_id,status", [(True, Status.INTERRUPTED), (False, Status.ACCEPTED)])
def test_ambiguous_stop_blocks_dispatch(rig, wrong_id, status):
    clock, b, _, c, station, d = rig
    b.admit(c)
    d.dispatch(c)
    station.stop = lambda cid: ExecutionEvent("wrong" if wrong_id else cid, status, clock[0])
    d.stop_active("test")
    assert b.statuses[c.command_id] == Status.UNKNOWN
    assert b.admit(replace(c, command_id="next")) == "unreconciled_command"
    assert station.dispatch_calls == 1


def test_old_scene_stop_decision_cannot_stop_new_command(rig):
    _, b, old, c, station, d = rig
    current = replace(old, sample_id=2, scene_version=1)
    b.observe(current)
    c = replace(c, sample_id=2, scene_version=1)
    b.admit(c)
    d.dispatch(c)
    d.stop_active("policy_abort", observation=old)
    assert b.statuses[c.command_id] == Status.ACCEPTED
    d.stop_active("policy_abort", observation=current)
    assert b.statuses[c.command_id] == Status.INTERRUPTED
