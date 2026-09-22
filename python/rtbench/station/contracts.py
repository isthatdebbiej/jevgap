from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
import uuid
from typing import Callable, Protocol

LOCAL_CLOCK = "local-monotonic:" + uuid.uuid4().hex


class CommandType(StrEnum):
    PICKUP = "pickup_request"
    CARTESIAN = "cartesian_target"
    JOINTS = "joint_trajectory"


class Status(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


TERMINAL = {Status.COMPLETED, Status.REJECTED, Status.FAILED, Status.INTERRUPTED}


@dataclass(frozen=True)
class ImageRef:
    key: str
    shape: tuple[int, ...]
    dtype: str


@dataclass(frozen=True)
class Observation:
    station_id: str
    episode_id: str
    sample_id: int
    scene_version: int
    captured_ns: int
    received_ns: int
    source_clock: str
    frame: str
    robot_state: dict
    poses: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    images: dict[str, ImageRef] = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    connected: bool = True


@dataclass(frozen=True)
class Capabilities:
    station_id: str
    simulation: bool
    observation_streams: tuple[str, ...]
    command_types: tuple[CommandType, ...]
    execution_feedback: bool
    stop_behavior: str
    frame: str = "robot_base"


@dataclass(frozen=True)
class PickupRequest:
    object_id: str
    position: tuple[float, float, float]
    kind: CommandType = field(default=CommandType.PICKUP, init=False)


@dataclass(frozen=True)
class CartesianTarget:
    position: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]
    kind: CommandType = field(default=CommandType.CARTESIAN, init=False)


@dataclass(frozen=True)
class JointTrajectory:
    joint_names: tuple[str, ...]
    positions: tuple[tuple[float, ...], ...]
    times_s: tuple[float, ...]
    kind: CommandType = field(default=CommandType.JOINTS, init=False)


@dataclass(frozen=True)
class Command:
    command_id: str
    task_id: str
    station_id: str
    episode_id: str
    sample_id: int
    scene_version: int
    captured_ns: int
    source_clock: str
    expires_ns: int
    frame: str
    action: PickupRequest | CartesianTarget | JointTrajectory


@dataclass(frozen=True)
class ExecutionEvent:
    command_id: str
    status: Status
    at_ns: int
    reason: str | None = None
    reconciled: bool = False


class ObservationSource(Protocol):
    capabilities: Capabilities

    def start(self, publish: Callable[[Observation], None]) -> None: ...
    def close(self) -> None: ...
    def measurements(self) -> dict: ...


class Controller(Protocol):
    def dispatch(self, command: Command) -> ExecutionEvent: ...
    def poll(self) -> list[ExecutionEvent]: ...
    def stop(self, command_id: str) -> ExecutionEvent: ...


def action_valid(action):
    def finite(values):
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in values)

    if isinstance(action, PickupRequest):
        return bool(action.object_id) and len(action.position) == 3 and finite(action.position)
    if isinstance(action, CartesianTarget):
        q = action.quaternion_xyzw
        return (
            len(action.position) == 3
            and finite(action.position)
            and len(q) == 4
            and finite(q)
            and abs(sum(x * x for x in q) - 1) < 1e-5
        )
    if isinstance(action, JointTrajectory):
        return (
            bool(action.joint_names)
            and len(set(action.joint_names)) == len(action.joint_names)
            and bool(action.times_s)
            and len(action.times_s) == len(action.positions)
            and finite(action.times_s)
            and action.times_s[0] >= 0
            and all(b > a for a, b in zip(action.times_s, action.times_s[1:]))
            and all(len(p) == len(action.joint_names) and finite(p) for p in action.positions)
        )
    return False


def record(value):
    return asdict(value)
