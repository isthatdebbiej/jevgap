"""One matched moving-cube pickup episode using the official YAM model."""

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import xml.etree.ElementTree as ET

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from yam_sim import scene, ROOT
from executors import Native, Rust
from settings import validate_credentials

ROT = np.diag([-1.0, 1.0, -1.0])
TOP = 0.12


class Pickup:
    def __init__(self, out):
        out.mkdir(parents=True, exist_ok=False)
        self.out = out
        scene(out / "base.xml")
        tree = ET.parse(out / "base.xml")
        root = tree.getroot()
        wb = root.find("worldbody")
        ET.SubElement(wb, "light", pos="1 0 2", dir="-1 0 -1", diffuse=".8 .8 .8")
        ET.SubElement(
            wb,
            "geom",
            name="table",
            type="box",
            pos=".40 0 .09",
            size=".22 .22 .03",
            rgba=".65 .70 .75 1",
            friction=".01 .001 .0001",
        )
        cube = ET.SubElement(wb, "body", name="cube", pos=f".25 -.035 {TOP + 0.019}")
        ET.SubElement(cube, "freejoint", name="cube_free")
        ET.SubElement(
            cube,
            "geom",
            name="cube_geom",
            type="box",
            size=".018 .018 .018",
            mass=".04",
            rgba=".9 .15 .06 1",
            friction="3 .1 .01",
            condim="6",
            solref=".002 1",
            solimp=".99 .99 .001",
        )
        # Primitive contact pads supplement the imported visual finger meshes.
        # They remain ordinary frictional collision geoms; no grasp constraint.
        for name, side in [("tip_left", 1), ("tip_right", -1)]:
            b = root.find(f'.//body[@name="{name}"]')
            for geom in b.findall("geom"):
                geom.set("contype", "0")
                geom.set("conaffinity", "0")
            quat = np.fromstring(b.get("quat"), sep=" ")
            mat = np.empty(9)
            mujoco.mju_quat2Mat(mat, quat)
            pos = np.fromstring(b.get("pos"), sep=" ")
            local = mat.reshape(3, 3).T @ (np.array([0, side * 0.050, -0.125]) - pos)
            inv = quat * np.array([1, -1, -1, -1])
            ET.SubElement(
                b,
                "geom",
                name=name + "_pad",
                type="box",
                pos=" ".join(map(str, local)),
                quat=" ".join(map(str, inv)),
                size=".025 .004 .022",
                friction="3 .1 .01",
                rgba=".12 .13 .15 1",
                condim="6",
                solref=".002 1",
                solimp=".99 .99 .001",
            )
        contact = root.find("contact")
        ET.SubElement(
            contact, "pair", geom1="table", geom2="cube_geom", friction=".005 .005 .001 .0001 .0001", condim="3"
        )
        tree.write(out / "scene.xml")
        self.m = mujoco.MjModel.from_xml_path(str(out / "scene.xml"))
        self.d = mujoco.MjData(self.m)
        self.m.opt.timestep = 0.001
        self.m.opt.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
        self.m.opt.impratio = 10
        self.m.opt.iterations = 100
        self.m.dof_damping[:8] = [6, 6, 6, 2, 2, 2, 2, 2]
        self.site = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_SITE, "grasp_site")
        self.cube = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, "cube")
        self.cgeom = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
        self.finger_geoms = [
            i for i in range(self.m.ngeom) if self.m.body(self.m.geom_bodyid[i]).name in {"tip_left", "tip_right"}
        ]
        self.ikdata = mujoco.MjData(self.m)
        self.q = np.array([0.0, 1.5, 1.8, -1.0, 0.0, 0.0])
        self.q = self.ik(np.array([0.25, -0.035, 0.22]), self.q)
        self.d.qpos[:6] = self.q
        self.d.qpos[6:8] = 0
        mujoco.mj_forward(self.m, self.d)
        self.phase = "waiting"
        self.phase_at = 0
        self.grip = 0
        self.accepted = False
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.frames = []
        self.events = []
        self.observations = {}
        self.obsid = 0
        self.pickup_s = None
        self.success_s = None
        self.bilateral_since = None
        self.lift_counter = 0
        self.last_ik = -1
        self.error = None

    def ik(self, pos, q):
        def residual(x):
            self.ikdata.qpos[:6] = x
            mujoco.mj_forward(self.m, self.ikdata)
            r = self.ikdata.site_xmat[self.site].reshape(3, 3)
            return np.r_[5 * (self.ikdata.site_xpos[self.site] - pos), 0.3 * (r[:, 2] - np.array([0, 0, -1]))]

        sol = least_squares(
            residual, q, bounds=(self.m.jnt_range[:6, 0] + 0.005, self.m.jnt_range[:6, 1] - 0.005), max_nfev=60
        )
        if np.linalg.norm(residual(sol.x)) > 0.03:
            rng = np.random.default_rng(42)
            for _ in range(30):
                initial = rng.uniform(self.m.jnt_range[:6, 0] + 0.01, self.m.jnt_range[:6, 1] - 0.01)
                candidate = least_squares(
                    residual,
                    initial,
                    bounds=(self.m.jnt_range[:6, 0] + 0.005, self.m.jnt_range[:6, 1] - 0.005),
                    max_nfev=150,
                )
                if np.linalg.norm(residual(candidate.x)) < np.linalg.norm(residual(sol.x)):
                    sol = candidate
                if np.linalg.norm(residual(sol.x)) < 0.005:
                    break
        if np.linalg.norm(residual(sol.x)) > 0.03:
            raise ValueError(f"unreachable grasp pose: {pos}, residual {residual(sol.x)}")
        return sol.x

    def contacts(self):
        touching = set()
        for c in self.d.contact:
            if c.dist > 0.001:
                continue
            if c.geom1 == self.cgeom and c.geom2 in self.finger_geoms:
                touching.add(int(self.m.geom_bodyid[c.geom2]))
            if c.geom2 == self.cgeom and c.geom1 in self.finger_geoms:
                touching.add(int(self.m.geom_bodyid[c.geom1]))
        return len(touching) == 2

    def transition(self, phase, t):
        self.phase = phase
        self.phase_at = t
        self.events.append({"kind": "phase", "phase": phase, "wall_s": t})

    def step(self, t):
        cube = self.d.xpos[self.cube].copy()
        bilateral = self.contacts()
        if self.accepted and self.phase == "waiting":
            self.transition("approach", t)
        pos = cube.copy()
        pos[2] = TOP + 0.10
        if self.phase == "approach" and np.linalg.norm(self.d.site_xpos[self.site] - pos) < 0.008:
            self.transition("descend", t)
        if self.phase in {"descend", "close"}:
            pos[2] = TOP + 0.010
        if self.phase == "descend" and np.linalg.norm(self.d.site_xpos[self.site] - pos) < 0.005:
            self.transition("close", t)
        if self.phase == "close":
            self.grip = min(0.0475, float(np.mean(self.d.qpos[6:8])) + (0.0005 if bilateral else 0.0001))
            if not bilateral:
                self.bilateral_since = None
            elif self.bilateral_since is None:
                self.bilateral_since = t
            if self.bilateral_since is not None and t - self.bilateral_since > 0.3 and t - self.phase_at > 1:
                self.lift_xy = cube[:2].copy()
                self.transition("lift", t)
        if self.phase in {"lift", "hold"}:
            self.grip = min(0.0475, float(np.mean(self.d.qpos[6:8])) + 0.0005)
            pos = (
                np.r_[self.lift_xy, TOP + 0.010 + min(0.09, (t - self.phase_at) * 0.025)]
                if self.phase == "lift"
                else self.holdpos.copy()
            )
            self.lift_counter = self.lift_counter + 1 if cube[2] > TOP + 0.05 and bilateral else 0
            if cube[2] > TOP + 0.05 and bilateral and self.pickup_s is None:
                self.pickup_s = t
            if self.lift_counter >= 300 and self.success_s is None:
                self.holdpos = pos.copy()
                self.success_s = t
                self.transition("hold", t)
        if self.phase != "waiting" and t - self.last_ik >= 0.05:
            self.q = self.ik(pos, self.q)
            self.last_ik = t
        self.d.qfrc_applied[:] = 0
        self.d.qfrc_applied[:6] = np.clip(
            np.array([100, 100, 100, 25, 25, 25]) * (self.q - self.d.qpos[:6]) + self.d.qfrc_bias[:6], -10, 10
        )
        self.d.qfrc_applied[6:8] = np.clip(1500 * (self.grip - self.d.qpos[6:8]) + self.d.qfrc_bias[6:8], -2, 2)
        # A free cube is driven slowly along the table until bilateral contact.
        # It is never welded, teleported, or parented to the gripper.
        self.d.xfrc_applied[self.cube, :] = 0
        if self.phase not in {"lift", "hold"} and not bilateral:
            self.d.xfrc_applied[self.cube, 1] = np.clip(0.8 * (0.008 - self.d.qvel[9]), -0.03, 0.03)
        mujoco.mj_step(self.m, self.d)
        if not np.isfinite(self.d.qpos).all():
            raise ValueError("nonfinite state")

    def state(self, now):
        self.obsid += 1
        cube = self.d.xpos[self.cube].tolist()
        s = {
            "observation_id": self.obsid,
            "scene_version": 0,
            "captured_ns": now,
            "committed_scene_version": 0 if self.accepted else -1,
            "target": cube,
            "cube_position_m": cube,
            "cube_velocity_m_s": self.d.qvel[8:11].tolist(),
            "phase": self.phase,
            "joint_positions": self.d.qpos[:6].tolist(),
            "task": "Pick up the slowly moving cube. Replan authorizes the shared visual-servo pickup controller to track the cube, close the gripper, and lift. Continue retains the running controller.",
            "observation": "Cube visible on table, within reach, no obstacles. The controller receives live cube observations and tracks motion continuously.",
            "current_plan": "Tracking pickup controller is running."
            if self.accepted
            else "No pickup controller has been authorized yet.",
        }
        self.observations[self.obsid] = now
        return s

    def offer(self, p):
        with self.lock:
            now = time.monotonic_ns()
            reason = None
            if p["source_scene_version"] != 0:
                reason = "scene_version"
            elif self.observations.get(p["source_observation_id"]) != p["source_captured_ns"]:
                reason = "observation"
            elif not 0 <= now - p["source_captured_ns"] <= 5e9:
                reason = "expired"
            elif self.stop.is_set():
                reason = "ended"
            elif p["decision"] == "replan":
                self.accepted = True
            elif p["decision"] == "abort":
                self.accepted = False
                self.transition("waiting", (now - self.begin) / 1e9)
            self.events.append(
                {"kind": "proposal", "decision": p["decision"], "reason": reason, "wall_s": (now - self.begin) / 1e9}
            )

    def run(self, duration, realtime, diagnostic):
        self.begin = time.monotonic_ns()
        try:
            for tick in range(int(duration * 1000)):
                with self.lock:
                    t = (time.monotonic_ns() - self.begin) / 1e9 if realtime else tick * 0.001
                    if diagnostic and t > 0.2:
                        self.accepted = True
                    self.step(t)
                    if tick % 50 == 0:
                        now = time.monotonic_ns()
                        self.latest = self.state(now)
                        self.frames.append(
                            {
                                "wall_s": t,
                                "sim_s": float(self.d.time),
                                "qpos": self.d.qpos.tolist(),
                                "phase": self.phase,
                                "cube_z": float(self.d.xpos[self.cube, 2]),
                                "bilateral_contact": self.contacts(),
                            }
                        )
                if realtime:
                    delay = self.begin / 1e9 + (tick + 1) * 0.001 - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
        except Exception as exc:
            self.error = type(exc).__name__ + ": " + str(exc)
        finally:
            self.stop.set()
            self.end = time.monotonic_ns()


def episode(out, system, diagnostic, duration):
    world = Pickup(out)
    results = []
    if diagnostic:
        world.run(duration, False, True)
    else:
        cfg = {
            "mode": "live",
            "entrypoint": "astra_provider:decide" if system == "A" else "jev_provider:decide",
            "max_calls": 30,
        }
        workflow = ROOT / "workflows/yam_pickup/workflow.json"
        runtime = Native(workflow, cfg, out / "native_trace") if system == "A" else Rust(workflow, cfg, out)
        thread = threading.Thread(target=world.run, args=(duration, True, False))
        thread.start()
        try:
            # Once authorized, the identical controller performs the pickup.
            while not world.stop.is_set() and not world.accepted and len(results) < 10:
                with world.lock:
                    s = dict(world.latest) if hasattr(world, "latest") else None
                if s is None:
                    time.sleep(0.01)
                    continue
                try:
                    r = runtime.run(s, len(results) + 1)
                except Exception as exc:
                    world.error = "provider/runtime: " + type(exc).__name__
                    break
                results.append(r)
                world.offer(r["outputs"]["bench.proposal" if system == "A" else "proposal"]["proposal"])
                world.stop.wait(0.2)
            thread.join()
        finally:
            runtime.close()
            thread.join()
    summary = {
        "system": system,
        "diagnostic": diagnostic,
        "pickup_s": world.pickup_s,
        "success_s": world.success_s,
        "success": bool(world.success_s is not None and world.d.xpos[world.cube, 2] > TOP + 0.05 and world.contacts()),
        "error": world.error,
        "model_calls": len(results),
        "final_phase": world.phase,
        "final_cube_z": float(world.d.xpos[world.cube, 2]),
        "physics_s": float(world.d.time),
        "wall_s": (world.end - world.begin) / 1e9,
        "pickup_definition": "cube center >5cm above table with both finger contacts; success holds for 300 physics steps",
        "controller": "common live-state tracking controller after model authorization; no welded or scripted lift",
    }
    for name, rows in [("trajectory", world.frames), ("events", world.events), ("workflows", results)]:
        (out / (name + ".jsonl")).write_text("".join(json.dumps(x) + "\n" for x in rows))
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--diagnostic", action="store_true")
    mode.add_argument("--live", action="store_true")
    p.add_argument("--duration", type=float, default=18)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    validate_credentials() if not a.diagnostic else None
    import hashlib

    config = {
        "duration_s": a.duration,
        "diagnostic": a.diagnostic,
        "systems": {"A": "Native GaP + Astra", "B": "GaP + Jev + custom Rust executor"},
        "models": {"A": "gpt-6-astra (low reasoning)", "B": "jev-1.13.0"},
        "moving_cube_command_speed_m_s": 0.008,
        "cube_mass_kg": 0.04,
        "cube_side_m": 0.036,
        "controller": "shared live-state tracking after model authorization",
        "collision_model": "experimental primitive finger pads, elliptic friction contacts; not validated hardware geometry",
        "source_sha256": {
            f: hashlib.sha256((ROOT / "scripts" / f).read_bytes()).hexdigest()
            for f in ["moving_cube.py", "executors.py", "astra_provider.py", "jev_provider.py"]
        },
    }
    (a.output / "config.json").write_text(json.dumps(config, indent=2))
    for s in ["diagnostic"] if a.diagnostic else ["A", "B"]:
        episode(a.output / s, s, a.diagnostic, a.duration)
