"""Shared admission and execution accounting; not an OS security sandbox."""

from collections import OrderedDict
from copy import deepcopy
import threading
import time
from .contracts import LOCAL_CLOCK, TERMINAL, Command, ExecutionEvent, Status, action_valid, record


class LatestSlot:
    def __init__(self):
        self.pending = None
        self.replaced = 0

    def put(self, state):
        if self.pending is not None:
            self.replaced += 1
        self.pending = state

    def take(self):
        value, self.pending = self.pending, None
        return value


class ImageBuffer:
    """Bounded process-local storage. Evicted references fail explicitly."""

    def __init__(self, max_bytes=16 * 1024 * 1024):
        if max_bytes <= 0:
            raise ValueError("image buffer must have positive capacity")
        self.max_bytes, self.size = max_bytes, 0
        self.items = OrderedDict()
        self.lock = threading.Lock()
        self.serial = 0

    def put(self, image):
        from .contracts import ImageRef

        image = image.copy()
        if image.nbytes > self.max_bytes:
            raise ValueError("image exceeds buffer capacity")
        with self.lock:
            while self.size + image.nbytes > self.max_bytes:
                _, old = self.items.popitem(last=False)
                self.size -= old.nbytes
            self.serial += 1
            key = str(self.serial)
            self.items[key] = image
            self.size += image.nbytes
            return ImageRef(key, tuple(image.shape), str(image.dtype))

    def get(self, ref):
        with self.lock:
            return self.items[ref.key].copy()


class Recorder:
    def __init__(self):
        self.rows = []
        self.lock = threading.Lock()

    def emit(self, kind, **data):
        with self.lock:
            self.rows.append(dict(kind=kind, **data))


class Boundary:
    def __init__(self, capabilities, recorder, age_ns=5_000_000_000, clock=time.monotonic_ns):
        self.capabilities, self.recorder, self.age_ns, self.clock = capabilities, recorder, age_ns, clock
        self.lock = threading.RLock()
        self.latest = None
        self.slot = LatestSlot()
        self.observations = OrderedDict()
        self.commands = {}
        self.statuses = {}
        self.active = None
        self.unknown = set()
        self.ended = False

    def observe(self, observation):
        with self.lock:
            o = deepcopy(observation)
            if o.station_id != self.capabilities.station_id:
                raise ValueError("wrong station")
            if self.latest and (
                o.episode_id != self.latest.episode_id
                or o.sample_id <= self.latest.sample_id
                or o.scene_version < self.latest.scene_version
            ):
                self.recorder.emit("observation_rejected", reason="out_of_order_or_episode", sample_id=o.sample_id)
                return
            self.latest = o
            self.observations[o.sample_id] = o
            while len(self.observations) > 256:
                self.observations.popitem(last=False)
            self.slot.put(o)
            self.recorder.emit("observation", **record(o))
            if not o.connected and self.active:
                self.event(ExecutionEvent(self.active, Status.UNKNOWN, self.clock(), "disconnected"))

    def take(self):
        with self.lock:
            return self.slot.take()

    def validate(self, command, *, running=False):
        now, o = self.clock(), self.latest
        if self.ended:
            return "episode_ended"
        if self.unknown:
            return "unreconciled_command"
        if o is None or not o.connected:
            return "disconnected_or_missing"
        if command.station_id != o.station_id or command.episode_id != o.episode_id:
            return "wrong_station_or_episode"
        if command.scene_version != o.scene_version:
            return "stale_scene" if command.scene_version < o.scene_version else "future_scene"
        if command.frame != self.capabilities.frame or o.frame != command.frame:
            return "coordinate_frame"
        if command.source_clock != LOCAL_CLOCK or o.source_clock != LOCAL_CLOCK:
            return "unmapped_clock"
        if not 0 <= now - o.captured_ns <= self.age_ns:
            return "stale_current_observation"
        if now >= command.expires_ns:
            return "expired_command"
        if not running:
            source = self.observations.get(command.sample_id)
            if source is None or (source.scene_version, source.captured_ns, source.source_clock) != (
                command.scene_version,
                command.captured_ns,
                command.source_clock,
            ):
                return "unknown_observation"
            if not 0 <= now - command.captured_ns <= self.age_ns:
                return "expired_observation"
        if not action_valid(command.action):
            return "invalid_action"
        if command.action.kind not in self.capabilities.command_types:
            return "unsupported_command"
        if self.active and self.active != command.command_id:
            return "busy"
        return None

    def admit(self, command: Command):
        with self.lock:
            self.recorder.emit("proposal", **record(command))
            reason = "duplicate_command" if command.command_id in self.commands else self.validate(command)
            self.recorder.emit("admission", command_id=command.command_id, at_ns=self.clock(), reason=reason)
            if command.command_id not in self.commands:
                self.commands[command.command_id] = command
                if reason:
                    self.event(ExecutionEvent(command.command_id, Status.REJECTED, self.clock(), reason))
            return reason

    def event(self, event):
        with self.lock:
            if event.command_id not in self.commands:
                self.recorder.emit("feedback_rejected", reason="unknown_command", event=record(event))
                return
            previous = self.statuses.get(event.command_id)
            allowed = {
                None: {Status.ACCEPTED, Status.REJECTED, Status.UNKNOWN},
                Status.ACCEPTED: {Status.RUNNING, Status.COMPLETED, Status.FAILED, Status.INTERRUPTED, Status.UNKNOWN},
                Status.RUNNING: {Status.COMPLETED, Status.FAILED, Status.INTERRUPTED, Status.UNKNOWN},
                Status.UNKNOWN: TERMINAL,
            }
            if event.status not in allowed.get(previous, set()) or (
                previous == Status.UNKNOWN and not event.reconciled
            ):
                self.recorder.emit(
                    "feedback_rejected", event=record(event), reason="invalid_transition_or_unreconciled"
                )
                return
            self.statuses[event.command_id] = event.status
            self.recorder.emit("execution", **record(event))
            if event.status == Status.UNKNOWN:
                self.unknown.add(event.command_id)
                self.active = event.command_id
            elif event.status in TERMINAL:
                self.unknown.discard(event.command_id)
                if self.active == event.command_id:
                    self.active = None
            else:
                self.active = event.command_id


class SimulationDispatcher:
    def __init__(self, boundary, controller):
        if not boundary.capabilities.simulation:
            raise ValueError("physical dispatch is not implemented")
        self.boundary, self.controller = boundary, controller

    def dispatch(self, command):
        b = self.boundary
        with b.lock:
            if command.command_id not in b.commands or command.command_id in b.statuses:
                return "not_admitted_or_duplicate"
            reason = b.validate(command)
            if reason:
                b.event(ExecutionEvent(command.command_id, Status.REJECTED, b.clock(), reason))
                return reason
            b.recorder.emit("dispatch", command_id=command.command_id, at_ns=b.clock())
            try:
                reply = self.controller.dispatch(command)
                if reply.command_id != command.command_id or reply.status not in {Status.ACCEPTED, Status.REJECTED}:
                    raise ValueError("ambiguous acknowledgement")
                b.recorder.emit("acknowledgement", **record(reply))
                b.event(reply)
            except Exception:
                b.event(ExecutionEvent(command.command_id, Status.UNKNOWN, b.clock(), "acknowledgement_missing"))
            return None

    def poll(self):
        b = self.boundary
        with b.lock:
            try:
                for event in self.controller.poll():
                    b.event(event)
                if b.active and b.active not in b.unknown:
                    command = b.commands[b.active]
                    reason = b.validate(command, running=True)
                    if reason:
                        b.recorder.emit("stop_requested", command_id=b.active, reason=reason, at_ns=b.clock())
                        b.event(self.controller.stop(b.active))
            except Exception:
                if b.active:
                    b.event(ExecutionEvent(b.active, Status.UNKNOWN, b.clock(), "feedback_unavailable"))

    def stop(self):
        b = self.boundary
        with b.lock:
            b.ended = True
        self.poll()
