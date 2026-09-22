"""MuJoCo-only station. No physical SDK controller is exposed."""

import threading
import time

from .contracts import Observation, ExecutionEvent, Status, LOCAL_CLOCK


class YamStation:
    def __init__(self, boundary, images, out, duration_s=3, perception="poses", change_s=1):
        from moving_cube import Pickup

        self.boundary, self.images, self.duration_s = boundary, images, duration_s
        self.capabilities = boundary.capabilities
        self.perception, self.change_s = perception, change_s
        self.active, self.running_sent = None, False
        self.latest_image = None
        self.version, self.sample_id = 0, 0
        self.error = None
        self.frames = []
        self.dispatch_calls = 0
        self.publish = lambda o: None
        self.stopped = threading.Event()
        self.thread = self.camera_thread = None
        owner = self

        class World(Pickup):
            def step(self, t):
                if owner.version == 0 and self.d.time >= owner.change_s:
                    owner.version = 1
                    self.drive_speed = -0.008
                    owner.observation()  # Invalidate queued proposals before any new controller update.
                command = owner.active
                observation = boundary.latest
                permitted = command is not None and boundary.validate(command, running=True) is None
                pose = observation.poses.get("cube") if observation else None
                permitted = permitted and pose is not None
                self.accepted = permitted
                super().step(t, target_position=pose, allow_tracking=permitted)

        self.world = World(out)
        self.world.lock = boundary.lock

    def observation(self):
        w = self.world
        now = time.monotonic_ns()
        self.sample_id += 1
        captured, version, images, calibration = now, self.version, {}, {}
        poses = {"cube": tuple(w.d.xpos[w.cube])}
        if self.perception == "rgbd":
            poses = {}
            if self.latest_image:
                captured, image_version, images, calibration = self.latest_image
                if image_version != self.version:
                    images = {}
        o = Observation(
            self.capabilities.station_id,
            "episode-1",
            self.sample_id,
            version,
            captured,
            now,
            LOCAL_CLOCK,
            "robot_base",
            {"joint_positions": w.d.qpos[:6].tolist()},
            poses,
            images,
            calibration,
        )
        self.publish(o)

    def camera_loop(self):
        import mujoco

        w = self.world
        renderer = None
        try:
            data = mujoco.MjData(w.m)
            renderer = mujoco.Renderer(w.m, height=160, width=160)
            camera = mujoco.mj_name2id(w.m, mujoco.mjtObj.mjOBJ_CAMERA, "bench_camera")
            while not self.stopped.is_set():
                with self.boundary.lock:
                    captured, version = time.monotonic_ns(), self.version
                    data.qpos[:] = w.d.qpos
                mujoco.mj_forward(w.m, data)
                renderer.update_scene(data, camera="bench_camera")
                rgb = renderer.render().copy()
                renderer.enable_depth_rendering()
                try:
                    depth = renderer.render().copy()
                finally:
                    renderer.disable_depth_rendering()
                refs = {"rgb": self.images.put(rgb), "depth": self.images.put(depth)}
                calibration = dict(
                    position=data.cam_xpos[camera].tolist(),
                    rotation=data.cam_xmat[camera].reshape(3, 3).tolist(),
                    fovy=float(w.m.cam_fovy[camera]),
                )
                with self.boundary.lock:
                    self.latest_image = (captured, version, refs, calibration)
                self.stopped.wait(0.05)
        except Exception as exc:
            self.error = type(exc).__name__
        finally:
            if renderer:
                renderer.close()

    def start(self, publish):
        self.publish = publish
        w = self.world
        w.begin = time.monotonic_ns()
        if self.perception == "rgbd":
            self.camera_thread = threading.Thread(target=self.camera_loop)
            self.camera_thread.start()

        def physics():
            try:
                for tick in range(int(self.duration_s * 1000)):
                    if self.stopped.is_set():
                        break
                    with self.boundary.lock:
                        t = (time.monotonic_ns() - w.begin) / 1e9
                        w.step(t)
                        if tick % 50 == 0:
                            self.observation()
                            self.frames.append(
                                dict(wall_s=t, sim_s=float(w.d.time), qpos=w.d.qpos.tolist(), phase=w.phase)
                            )
                    self.stopped.wait(max(0, w.begin / 1e9 + (tick + 1) * 0.001 - time.monotonic()))
            except Exception as exc:
                self.error = type(exc).__name__
            finally:
                w.end = time.monotonic_ns()
                self.stopped.set()

        self.thread = threading.Thread(target=physics)
        self.thread.start()

    def dispatch(self, command):
        if command.action.object_id != "cube":
            return ExecutionEvent(command.command_id, Status.REJECTED, time.monotonic_ns(), "unsupported_object")
        if self.stopped.is_set():
            return ExecutionEvent(command.command_id, Status.REJECTED, time.monotonic_ns(), "simulation_ended")
        self.dispatch_calls += 1
        self.active, self.running_sent = command, False
        return ExecutionEvent(command.command_id, Status.ACCEPTED, time.monotonic_ns())

    def poll(self):
        if not self.active:
            return []
        from moving_cube import TOP

        w = self.world
        if w.success_s is not None and w.contacts() and w.d.xpos[w.cube, 2] > TOP + 0.05:
            event = ExecutionEvent(self.active.command_id, Status.COMPLETED, time.monotonic_ns())
            self.active = None
            return [event]
        if self.stopped.is_set():
            return [self.stop(self.active.command_id)]
        if not self.running_sent:
            self.running_sent = True
            return [ExecutionEvent(self.active.command_id, Status.RUNNING, time.monotonic_ns())]
        return []

    def stop(self, command_id):
        self.active = None
        self.world.accepted = False
        return ExecutionEvent(command_id, Status.INTERRUPTED, time.monotonic_ns(), "simulation_hold")

    def measurements(self):
        from moving_cube import TOP

        w = self.world
        wall = (getattr(w, "end", time.monotonic_ns()) - w.begin) / 1e9
        return dict(
            physics_s=float(w.d.time),
            wall_s=wall,
            real_time_factor=float(w.d.time) / max(wall, 1e-9),
            pickup_success=bool(w.success_s is not None and w.contacts() and w.d.xpos[w.cube, 2] > TOP + 0.05),
            success_s=w.success_s,
            error=self.error,
            dispatch_calls=self.dispatch_calls,
            perception=self.perception,
            scene_change="scripted motion reversal",
        )

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join()
        if self.camera_thread:
            self.camera_thread.join()
