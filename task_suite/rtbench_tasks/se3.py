"""SE3 0.0.1 lifecycle bridge. Perception/motion/evidence come from a calibrated driver.

The SDK callback never waits for the model. A single GaP worker requests motions;
the SDK thread submits chunks and the driver verifies effects on later observations.
"""
import copy
import importlib
import math
import threading
import time
from dataclasses import dataclass

import numpy as np

from .contracts import Evidence, Observation, Receipt
from .config import positive


@dataclass(frozen=True)
class JointPlan:
    """Complete finite trajectory; each arm maps to (joint rows, gripper rows)."""
    arms: dict
    rate: float


@dataclass(frozen=True)
class Verification:
    status: str  # pending | completed | failed
    feedback: str = ""


class SDKTypes:
    def __init__(self):
        from se3labs.interface.eval.arm import MotorizedArm_ActionChunk, MotorizedArm_JointPose
        from se3labs.interface.eval.station import Station_ActionChunk, Station_JointPose
        from se3labs.interface.eval.policy import EndEpisode
        self.ArmChunk, self.ArmPose = MotorizedArm_ActionChunk, MotorizedArm_JointPose
        self.Chunk, self.Pose, self.EndEpisode = Station_ActionChunk, Station_JointPose, EndEpisode

    def start_pose(self, config, station):
        arms = {}
        for name, pose in config.items():
            joints, gripper = np.asarray(pose["joints"], dtype=np.float32), np.asarray(pose["gripper"], dtype=np.float32)
            if not np.isfinite(joints).all() or not np.isfinite(gripper).all() or (gripper < 0).any() or (gripper > 1).any():
                raise ValueError("invalid start pose values")
            arms[name] = self.ArmPose(joints, gripper)
        result = self.Pose(arms)
        result.validate(station)
        return result

    def chunk(self, plan, station, timestamp):
        if not isinstance(plan, JointPlan) or not math.isfinite(plan.rate) or plan.rate <= 0 or not math.isfinite(timestamp):
            raise ValueError("invalid joint plan or station time")
        arms = {}
        for name, (joints, gripper) in plan.arms.items():
            q, g = np.asarray(joints, dtype=np.float32), np.asarray(gripper, dtype=np.float32)
            if q.ndim != 2 or g.ndim != 2 or not len(q) or len(q) > 10000 or len(q) != len(g):
                raise ValueError("invalid action horizon")
            if not np.isfinite(q).all() or not np.isfinite(g).all() or (g < 0).any() or (g > 1).any():
                raise ValueError("nonfinite joint target or invalid gripper fraction")
            arms[name] = self.ArmChunk(q, g)
        result = self.Chunk(timestamp=timestamp, rate=plan.rate, arms=arms)
        result.validate(station)
        return result


def load_driver(entry, *, config_path, calibration_id):
    module, name = entry.split(":", 1)
    driver = getattr(importlib.import_module(module), name)(config_path=config_path)
    if driver.calibration_id != calibration_id:
        driver.close()
        raise ValueError("driver calibration does not match station configuration")
    return driver


class SE3Backend:
    mode = "se3"

    def __init__(self, driver, station, *, sdk=None, command_timeout_s=30, observation_timeout_s=10, max_age_ms=2000):
        self.driver, self.station, self.sdk = driver, station, sdk or SDKTypes()
        for name, value in (("command_timeout_s", command_timeout_s), ("observation_timeout_s", observation_timeout_s), ("max_age_ms", max_age_ms)):
            positive(value, name)
        self.capabilities = frozenset(driver.capabilities)
        self.command_timeout_s, self.observation_timeout_s = command_timeout_s, observation_timeout_s
        self.max_age_ms = max_age_ms
        self.cv = threading.Condition()
        self.closed = False
        self.sequence = 0
        self.last_read_sequence = 0
        self.latest = None
        self.latest_ns = 0
        self.station_time = None
        self.arm_times = {}
        self.clock_offset_ns = None
        self.pending = None
        self.sent_sequence = None
        self.active = False
        self.proof = {}

    def reset(self, scenario):
        self.scenario = scenario
        self.driver.reset(scenario)

    def publish(self, raw):
        if set(raw.arms) != set(self.station.arms):
            raise ValueError("observation arms differ from station specification")
        timestamps = [a.timestamp for a in raw.arms.values()]
        if not timestamps or any(not math.isfinite(t) for t in timestamps):
            raise ValueError("invalid station timestamps")
        stamp = max(timestamps)
        if (stamp - min(timestamps)) * 1000 > self.max_age_ms:
            raise ValueError("arm observations are not synchronized")
        received_ns = time.monotonic_ns()
        with self.cv:
            if self.closed:
                return
            if any(name in self.arm_times and a.timestamp < self.arm_times[name] for name, a in raw.arms.items()):
                raise ValueError("station clock moved backwards")
            if self.station_time == stamp:
                return  # Repeated packets do not refresh stale evidence.
            offset = received_ns - round(stamp * 1e9)
            self.clock_offset_ns = offset if self.clock_offset_ns is None else min(self.clock_offset_ns, offset)
            self.latest_ns = round(min(timestamps) * 1e9) + self.clock_offset_ns
            self.arm_times = {name: a.timestamp for name, a in raw.arms.items()}
            self.station_time, self.latest = stamp, raw
            self.sequence += 1
            self.cv.notify_all()

    def _wait_observation(self, after, timeout):
        with self.cv:
            available = self.cv.wait_for(lambda: self.closed or self.sequence > after, timeout=timeout)
            if self.closed:
                raise RuntimeError("station episode closed")
            if not available:
                raise TimeoutError("station observation timeout")
            return self.sequence, self.latest_ns, self.latest

    def observe(self):
        seq, captured, raw = self._wait_observation(self.last_read_sequence, self.observation_timeout_s)
        self.last_read_sequence = seq
        visible = self.driver.observe(raw)
        return Observation(self.scenario.id, seq, captured, copy.deepcopy(visible))

    def execute(self, action, command_id, observation):
        with self.cv:
            if self.closed or self.active:
                raise RuntimeError("closed station or unresolved command")
            self.active = True
            raw = self.latest
            source_timestamp, source_captured_ns = self.station_time, self.latest_ns
        # Driver must re-perceive/validate the action against this newer raw frame.
        plan = self.driver.plan(action, raw)
        with self.cv:
            if self.closed:
                raise RuntimeError("station closed during planning")
            if time.monotonic_ns() - source_captured_ns > self.max_age_ms * 1_000_000:
                raise TimeoutError("planning observation expired")
            chunk = self.sdk.chunk(plan, self.station, source_timestamp)
            self.driver.validate_plan(action, plan, self.latest)
            self.pending = chunk
            self.pending_captured_ns = source_captured_ns
            self.sent_sequence = None
            sent = self.cv.wait_for(lambda: self.closed or self.sent_sequence is not None, self.command_timeout_s)
            if self.closed or not sent:
                self.closed = True
                self.pending = None
                self.cv.notify_all()
                raise TimeoutError("action submission was not observed")
            after = self.sent_sequence
        deadline = time.monotonic() + self.command_timeout_s
        while time.monotonic() < deadline:
            seq, _, raw = self._wait_observation(after, max(0.001, deadline - time.monotonic()))
            after = seq
            result = self.driver.verify(action, command_id, raw)
            if not isinstance(result, Verification) or result.status not in {"pending", "completed", "failed"}:
                raise ValueError("invalid measured verification")
            if result.status == "pending":
                continue
            self.last_read_sequence = seq
            self.proof = {"command_id": command_id, "verified": result.status == "completed"}
            # Only a measured terminal effect permits another command.
            if result.status == "completed":
                self.active = False
            return Receipt(command_id, result.status, result.status == "completed", seq, result.feedback)
        raise TimeoutError("physical completion was not verified")

    def next_chunk(self):
        with self.cv:
            if self.closed or self.pending is None:
                return None
            if time.monotonic_ns() - self.pending_captured_ns > self.max_age_ms * 1_000_000:
                raise TimeoutError("queued action observation expired")
            result, self.pending = self.pending, None
            # Timestamp corresponds to the observation used for planning, never local wall time.
            self.sent_sequence = self.sequence
            self.cv.notify_all()
            return result

    def checkpoint(self):
        return dict(self.proof)

    def evidence(self):
        result = self.driver.evidence()
        if not isinstance(result, Evidence) or result.calibration_id != self.driver.calibration_id:
            raise ValueError("driver returned invalid evaluation evidence")
        return result

    def close(self):
        with self.cv:
            self.closed = True
            self.pending = None
            self.cv.notify_all()


class GraphPolicy:
    """Duck-types the SDK Policy contract; one SDK JobRequest per scored scenario."""
    def __init__(self, scenario, policy, driver, station_config, graph_dir, output_dir, limits, *, sdk=None):
        self.scenario, self.policy, self.driver = scenario, policy, driver
        self.config, self.graph_dir, self.output_dir, self.limits = station_config, graph_dir, output_dir, limits
        self.sdk = sdk or SDKTypes()
        self.backend = None
        self.worker = None
        self.done = threading.Event()
        self.report = None
        self.error = None
        self.cleaned = False

    def initialize(self, station, task):
        if self.backend is not None or self.cleaned:
            raise RuntimeError("create a fresh GraphPolicy for every episode")
        self.driver.validate_station(station)
        pose = self.sdk.start_pose(self.config["start_pose"], station)
        self.driver.validate_start_pose(pose)
        self.backend = SE3Backend(self.driver, station, sdk=self.sdk,
                                  command_timeout_s=self.limits["command_timeout_s"], max_age_ms=self.limits["max_age_ms"])
        # Initial instruction comes from the scenario once, not an SDK-cached prompt.
        return pose

    def _run(self):
        from .runtime import run_episode
        try:
            limits = {k: v for k, v in self.limits.items() if k != "command_timeout_s"}
            self.report = run_episode(self.scenario, self.backend, self.policy, self.graph_dir,
                                      self.output_dir, allow_hardware=True, **limits)
        except Exception as exc:
            self.error = type(exc).__name__
        finally:
            self.backend.close()
            self.done.set()

    def infer(self, observation):
        if self.done.is_set():
            raise self.sdk.EndEpisode()
        try:
            self.backend.publish(observation)
            if self.worker is None:
                self.worker = threading.Thread(target=self._run, name="jevgap-episode", daemon=True)
                self.worker.start()
            return self.backend.next_chunk()
        except self.sdk.EndEpisode:
            raise
        except Exception as exc:
            # SDK ordinary infer errors continue the old chunk. Explicitly end instead.
            self.error = type(exc).__name__
            if self.backend:
                self.backend.close()
            self.done.set()
            raise self.sdk.EndEpisode() from None

    def reset(self):
        if self.cleaned:
            return
        self.cleaned = True
        self.done.set()
        if self.backend:
            self.backend.close()
        if self.worker:
            self.worker.join(timeout=2)
            if self.worker.is_alive():
                self.error = "worker_still_running"
        # Driver cleanup must be bounded; it is not a physical stop acknowledgement.
        self.driver.close()


def task_spec(scenario, station_config, max_rollout_time):
    from se3labs.interface.eval.task import Task_Spec, Task_ScoreSheet, Task_ScoreItem, Task_ScoreKind
    from .catalog import TASKS
    return Task_Spec(name=scenario.task_id, description=TASKS[scenario.task_id].instruction,
                     reset_instruction=station_config["reset_instructions"][scenario.task_id],
                     instruction=scenario.instruction, max_rollout_time=max_rollout_time,
                     scoring=Task_ScoreSheet(success=Task_ScoreItem("task_success",
                         "Did the task satisfy every criterion in the frozen task rubric, including returning home?",
                         Task_ScoreKind.Binary)))
