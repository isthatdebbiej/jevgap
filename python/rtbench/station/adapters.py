from dataclasses import replace
import threading
import time
from .contracts import Capabilities, CommandType, ExecutionEvent, LOCAL_CLOCK, Observation, Status


class PosesPerception:
    def process(self, observation):
        return observation


class RGBDPerception:
    def __init__(self, images):
        self.images = images
        from camera_state import estimate_cube

        self.estimate_cube = estimate_cube

    def process(self, observation):
        import numpy as np

        try:
            c = observation.calibration
            pose, _ = self.estimate_cube(
                self.images.get(observation.images["rgb"]),
                self.images.get(observation.images["depth"]),
                np.array(c["position"]),
                np.array(c["rotation"]),
                c["fovy"],
            )
        except (KeyError, ValueError):
            pose = None
        return replace(observation, poses={"cube": tuple(pose)} if pose else {})


class FakeStation:
    """Scriptable station; advance() supports deterministic clock-driven tests."""

    def __init__(self, boundary, images, duration_s=1, faults=None, perception="poses", clock=time.monotonic_ns):
        self.boundary, self.images, self.duration_s = boundary, images, duration_s
        self.capabilities = boundary.capabilities
        self.faults, self.perception, self.clock = faults or {}, perception, clock
        self.connected = True
        self.sample_id, self.ticks, self.dispatch_calls = 0, 0, 0
        self.active, self.dispatched_ns = None, None
        self.executed = set()
        self.running_sent = False
        self.stop_event = threading.Event()
        self.thread = None
        self.begin = clock()
        self.publish = lambda o: None

    def advance(self, now):
        elapsed = (now - self.begin) / 1e9
        self.ticks += 1
        dis = self.faults.get("disconnect_s", float("inf"))
        rec = self.faults.get("reconnect_s", float("inf"))
        self.connected = not dis <= elapsed < rec
        if self.active and self.connected and now - self.dispatched_ns >= 300_000_000:
            self.executed.add(self.active)
        if elapsed < self.faults.get("missing_until_s", 0):
            return
        self.sample_id += 1
        scene = int(elapsed >= self.faults.get("scene_change_s", float("inf")))
        poses, refs, calibration = {"cube": (0.25, -0.035, 0.139)}, {}, {}
        if self.perception == "rgbd":
            import numpy as np

            rgb = np.zeros((20, 20, 3), dtype=np.uint8)
            rgb[8:12, 8:12, 0] = 255
            refs = {"rgb": self.images.put(rgb), "depth": self.images.put(np.ones((20, 20)) * 0.5)}
            calibration = dict(position=[0.25, -0.035, 0.657], rotation=np.eye(3).tolist(), fovy=45)
            poses = {}
        observation = Observation(
            self.capabilities.station_id,
            "episode-1",
            self.sample_id,
            scene,
            now - int(self.faults.get("observation_delay_s", 0) * 1e9),
            now,
            self.faults.get("source_clock", LOCAL_CLOCK),
            "robot_base",
            {"joint_positions": [0.0] * 6},
            poses=poses,
            images=refs,
            calibration=calibration,
            connected=self.connected,
        )
        self.publish(observation)

    def start(self, publish):
        self.publish = publish
        self.begin = self.clock()

        def loop():
            while not self.stop_event.is_set() and (self.clock() - self.begin) / 1e9 < self.duration_s:
                with self.boundary.lock:
                    self.advance(self.clock())
                self.stop_event.wait(0.02)

        self.thread = threading.Thread(target=loop)
        self.thread.start()

    def dispatch(self, command):
        self.dispatch_calls += 1
        if command.action.object_id != "cube":
            return ExecutionEvent(command.command_id, Status.REJECTED, self.clock(), "unsupported_object")
        if not self.connected:
            raise ConnectionError()
        self.active, self.dispatched_ns = command.command_id, self.clock()
        self.running_sent = False
        if self.faults.get("ack_loss"):
            raise TimeoutError()
        return ExecutionEvent(command.command_id, Status.ACCEPTED, self.clock())

    def poll(self):
        if not self.connected:
            raise ConnectionError()
        if not self.active:
            return []
        if self.active in self.executed:
            event = ExecutionEvent(self.active, Status.COMPLETED, self.clock())
            self.active = None
            return [event]
        if not self.running_sent:
            self.running_sent = True
            return [ExecutionEvent(self.active, Status.RUNNING, self.clock())]
        return []

    def reconcile(self, command_id):
        if not self.connected:
            raise ConnectionError()
        status = Status.COMPLETED if command_id in self.executed else Status.INTERRUPTED
        if self.active == command_id:
            self.active = None
        return ExecutionEvent(command_id, status, self.clock(), "station_state_checked", reconciled=True)

    def stop(self, command_id):
        if not self.connected:
            raise ConnectionError()
        self.active = None
        return ExecutionEvent(command_id, Status.INTERRUPTED, self.clock(), "simulation_hold")

    def measurements(self):
        return dict(
            observation_ticks=self.ticks, independently_completed=len(self.executed), dispatch_calls=self.dispatch_calls
        )

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()


def simulation_capabilities(station_id):
    return Capabilities(
        station_id,
        True,
        ("robot_state", "object_poses", "rgbd"),
        (CommandType.PICKUP,),
        True,
        "hold simulated joint target",
    )
