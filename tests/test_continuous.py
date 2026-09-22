from continuous import LatestSlot, rejection
from camera_state import estimate_cube
import numpy as np
from continuous import ContinuousPickup
from moving_cube import Pickup
from types import SimpleNamespace
import threading


def test_pending_replacement_keeps_newest():
    slot = LatestSlot()
    for i in range(100):
        slot.put({"observation_id": i})
    assert slot.replaced == 99
    assert slot.take() == {"observation_id": 99}
    assert slot.take() is None


def test_gate_rechecks_scene_and_observation():
    p = dict(source_scene_version=2, source_observation_id=4, source_captured_ns=100)
    observations = {4: (100, 2)}
    assert rejection(p, observations, 2, 120, 30) is None
    assert rejection(p, observations, 3, 120, 30) == "stale_scene"
    assert rejection(p, observations, 1, 120, 30) == "future_scene"
    assert rejection(p, observations, 2, 140, 30) == "expired"
    assert rejection(p, observations, 2, 90, 30) == "expired"
    assert rejection(p, {}, 2, 120, 30) == "unknown_observation"
    assert rejection(p, observations, 2, 120, 30, True) == "ended"


def test_camera_projection_and_missing_object():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    depth = np.ones((20, 20)) * 0.5
    assert estimate_cube(rgb, depth, np.array([0, 0, 1]), np.eye(3), 45)[0] is None
    rgb[8:12, 8:12, 0] = 255
    pose, confidence = estimate_cube(rgb, depth, np.array([0, 0, 1]), np.eye(3), 45)
    assert np.allclose(pose, [0, 0, 0.482])
    assert confidence > 0


def test_admitted_command_is_rechecked_after_scene_change_and_lease_expiry(monkeypatch):
    clock = [1_000_000_000]
    monkeypatch.setattr("continuous.time.monotonic_ns", lambda: clock[0])
    commands = []
    monkeypatch.setattr(Pickup, "step", lambda self, t, **kw: commands.append(kw["allow_tracking"]))
    w = ContinuousPickup.__new__(ContinuousPickup)
    w.args = SimpleNamespace(age_s=5, lease_s=1, change_s=1)
    w.lock, w.stop = threading.RLock(), threading.Event()
    w.version, w.committed, w.begin = 0, -1, 0
    w.observations = {1: (clock[0], 0)}
    w.events, w.authorized, w.lease_ns = [], False, 0
    w.estimate, w.observation_ready_ns = [0, 0, 0], clock[0]
    w.changed, w.d = True, SimpleNamespace(time=0)
    w.ticks, w.paused_ticks, w.command_version = 0, 0, None
    w.change_ns, w.fresh_ns = None, None
    p = dict(source_scene_version=0, source_observation_id=1, source_captured_ns=clock[0], decision="replan")
    w.offer(p)
    w.step(1)
    assert commands[-1] is True
    w.version = 1
    w.step(1.1)
    assert commands[-1] is False
    w.observations[2] = (clock[0], 1)
    w.offer(dict(p, source_scene_version=1, source_observation_id=2))
    w.step(1.2)
    assert commands[-1] is True
    clock[0] += 1_000_000_001
    w.observation_ready_ns = clock[0]  # Fresh perception cannot renew an expired authorization.
    w.step(2.2)
    assert commands[-1] is False
