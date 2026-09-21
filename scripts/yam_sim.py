"""YAM dynamics integration pilot. Joint-space reaching, not a grasp benchmark."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
import xml.etree.ElementTree as ET

os.environ.setdefault("MUJOCO_GL", "egl")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/i2rt"))
import mujoco
import numpy as np
from executors import Native, Rust
from settings import validate_credentials

Q0 = np.array([0.0, 1.0, 1.7, -0.4, 0.0, 0.0])


def scene(path):
    from unittest.mock import patch
    from i2rt.robots.get_robot import get_yam_robot
    from i2rt.robots.utils import ArmType, GripperType

    with patch("i2rt.motor_drivers.can_interface.CanInterface.__init__", side_effect=AssertionError("CAN forbidden")):
        robot = get_yam_robot(arm_type=ArmType.YAM, gripper_type=GripperType.LINEAR_4310, sim=True)
    tree = ET.parse(robot.xml_path)
    robot.close()
    # The SDK's adjacent base/link1 visual meshes overlap at the bearing.
    # Exclude this pair explicitly for free-space dynamics; retain other contacts.
    contact = tree.getroot().find("contact")
    if contact is None:
        contact = ET.SubElement(tree.getroot(), "contact")
    ET.SubElement(contact, "exclude", body1="base", body2="link1")
    wb = tree.getroot().find("worldbody")
    ET.SubElement(wb, "light", pos="0 -1 2", dir="0 0 -1")
    ET.SubElement(wb, "geom", name="floor", type="plane", size="2 2 .02", pos="0 0 -.025", rgba=".85 .88 .9 1")
    tree.write(path)
    return mujoco.MjModel.from_xml_path(str(path))


class World:
    def __init__(self, model, seed, condition, duration=12, age_s=5):
        self.model = model
        self.data = mujoco.MjData(model)
        self.model.opt.timestep = 0.001
        # Integrate velocity damping implicitly; explicit damping is unstable on
        # the low-inertia wrist. This is a benchmark controller, not SDK fidelity.
        self.model.dof_damping[:6] = np.array([5, 5, 5, 1.5, 1.5, 1.5])
        self.model.dof_damping[6:] = 1
        self.data.qpos[:6] = Q0
        mujoco.mj_forward(model, self.data)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.duration = duration
        self.age_ns = int(age_s * 1e9)
        rng = np.random.default_rng(seed)
        self.first = Q0 + np.array([0.2, 0.08, -0.08, 0.05, 0.08, 0.05]) + rng.uniform(-0.02, 0.02, 6)
        self.second = Q0 + np.array([-0.2, -0.08, 0.08, -0.05, -0.08, -0.05]) + rng.uniform(-0.02, 0.02, 6)
        self.target = self.first.copy()
        self.command = Q0.copy()
        self.scene_version = 0
        self.committed = -1
        self.change_at = {"static": None, "early": 0.25, "late": 2.0}[condition]
        self.change_ns = None
        self.fresh_ns = None
        self.captured = {}
        self.observation_id = 0
        self.pending = None
        self.events = []
        self.frames = []
        self.error = None
        self.stable = 0
        self.reached_ns = None
        self.control_ticks = 0
        self.no_current_target_ticks = 0

    def start(self):
        self.begin = time.monotonic_ns()
        self.thread = threading.Thread(target=self.physics, daemon=True)
        self.thread.start()

    def physics(self):
        try:
            tick = 0
            kp = np.array([80, 80, 80, 10, 10, 10])
            kd = np.array([5, 5, 5, 1.5, 1.5, 1.5])
            while not self.stop.is_set():
                now = time.monotonic_ns()
                elapsed = (now - self.begin) / 1e9
                if elapsed >= self.duration:
                    break
                with self.lock:
                    if self.change_at is not None and self.change_ns is None and elapsed >= self.change_at:
                        self.target = self.second.copy()
                        self.scene_version += 1
                        self.change_ns = now
                        self.stable = 0
                        self.reached_ns = None
                        self.events.append(
                            {"kind": "detected_change", "time_ns": now, "scene_version": self.scene_version}
                        )
                    if self.pending is not None:
                        proposal = self.pending
                        self.pending = None
                        reason = self.validate(proposal, now)
                        if reason is None:
                            if proposal["decision"] == "replan":
                                self.command = np.array(proposal["target"])
                                self.committed = proposal["source_scene_version"]
                            elif proposal["decision"] == "abort":
                                self.command = self.data.qpos[:6].copy()
                            if (
                                proposal["decision"] in {"continue", "replan"}
                                and self.committed == self.scene_version
                                and self.fresh_ns is None
                                and self.change_ns is not None
                            ):
                                self.fresh_ns = now
                            self.events.append(
                                {
                                    "kind": "dispatch",
                                    "time_ns": now,
                                    "decision": proposal["decision"],
                                    "age_ms": (now - proposal["source_captured_ns"]) / 1e6,
                                }
                            )
                        else:
                            self.events.append({"kind": "dispatch_reject", "reason": reason, "time_ns": now})
                    self.control_ticks += 1
                    self.no_current_target_ticks += int(self.committed != self.scene_version)
                    # Ten physical steps per 10ms wall tick. No command-time qpos teleportation.
                    for _ in range(10):
                        self.data.qfrc_applied[:] = 0
                        self.data.qfrc_applied[:6] = np.clip(
                            kp * (self.command - self.data.qpos[:6]) + self.data.qfrc_bias[:6], -10, 10
                        )
                        self.data.qfrc_applied[6:] = np.clip(-20 * self.data.qpos[6:] + self.data.qfrc_bias[6:], -1, 1)
                        mujoco.mj_step(self.model, self.data)
                    if not np.isfinite(self.data.qpos).all():
                        raise RuntimeError("nonfinite dynamics")
                    err = float(np.max(np.abs(self.data.qpos[:6] - self.target)))
                    self.stable = self.stable + 1 if err < 0.04 and self.committed == self.scene_version else 0
                    if self.stable >= 25 and self.reached_ns is None:
                        self.reached_ns = now
                    if tick % 5 == 0:
                        self.frames.append(
                            {
                                "wall_s": elapsed,
                                "sim_s": float(self.data.time),
                                "qpos": self.data.qpos.tolist(),
                                "target": self.target.tolist(),
                                "error_rad": err,
                                "scene_version": self.scene_version,
                            }
                        )
                        self.observation_id += 1
                        self.captured[self.observation_id] = (now, self.scene_version)
                        self.latest = self.state(now)
                tick += 1
                # Fixed pacing; simulation slows under overload and the achieved factor is reported.
                delay = self.begin / 1e9 + tick * 0.01 - time.monotonic()
                if delay > 0:
                    self.stop.wait(delay)
        except Exception as exc:
            self.error = type(exc).__name__
        finally:
            self.end = time.monotonic_ns()
            self.stop.set()

    def state(self, now):
        return {
            "observation_id": self.observation_id,
            "scene_version": self.scene_version,
            "committed_scene_version": self.committed,
            "captured_ns": now,
            "target": self.target.tolist(),
            "joint_positions": self.data.qpos[:6].tolist(),
            "observation": "Clear simulated joint-state observation. Target is reachable. No obstacles or unsafe condition.",
            "current_plan": (
                "No target plan exists yet."
                if self.committed < 0
                else "The active plan is for the current target."
                if self.committed == self.scene_version
                else "Target moved; the active plan is for the previous target."
            ),
            "task": "Reach the target joint pose. Replan installs the observed target as the controller goal; continue keeps the existing goal.",
        }

    def observe(self):
        with self.lock:
            return dict(self.latest) if hasattr(self, "latest") else None

    def validate(self, p, now):
        version = p.get("source_scene_version")
        if version != self.scene_version:
            return (
                "stale_scene" if isinstance(version, int) and version < self.scene_version else "unknown_future_scene"
            )
        if self.captured.get(p.get("source_observation_id")) != (p.get("source_captured_ns"), version):
            return "unknown_observation"
        if not 0 <= now - p["source_captured_ns"] <= self.age_ns:
            return "expired"
        if p.get("decision") not in {"continue", "replan", "reperceive", "abort"}:
            return "invalid_decision"
        target = np.array(p.get("target", []))
        if target.shape != (6,) or not np.isfinite(target).all():
            return "invalid_target"
        if np.any(target < self.model.jnt_range[:6, 0]) or np.any(target > self.model.jnt_range[:6, 1]):
            return "joint_limits"
        return None

    def offer(self, p):
        with self.lock:
            now = time.monotonic_ns()
            reason = self.validate(p, now)
            if self.stop.is_set():
                reason = "episode_ended"
            if reason is None and self.pending is not None:
                reason = "queue_full"
            self.events.append(
                {
                    "kind": "admission" if reason is None else "reject",
                    "time_ns": now,
                    "reason": reason,
                    "decision": p.get("decision"),
                    "age_ms": (now - p["source_captured_ns"]) / 1e6,
                }
            )
            if reason is None:
                self.pending = p
            return reason


def trial(output, system, seed, condition, diagnostic, duration):
    output.mkdir(parents=True, exist_ok=False)
    model = scene(output / "scene.xml")
    cfg = (
        {"mode": "diagnostic", "max_calls": 100, "diagnostic_delay_s": 0.1}
        if diagnostic
        else {
            "mode": "live",
            "entrypoint": "astra_provider:decide" if system == "A" else "jev_provider:decide",
            "max_calls": 30,
        }
    )
    workflow = ROOT / "workflows/yam_pickup/workflow.json"
    executor = Native(workflow, cfg, output / "native_trace") if system == "A" else Rust(workflow, cfg, output)
    world = World(model, seed, condition, duration)
    runs = []
    failures = []
    world.start()
    try:
        while not world.stop.is_set() and len(runs) + len(failures) < 30:
            state = world.observe()
            if state is None:
                time.sleep(0.01)
                continue
            try:
                result = executor.run(state, len(runs) + 1)
                p = result["outputs"]["bench.proposal" if system == "A" else "proposal"]["proposal"]
                result["admission_rejection"] = world.offer(p)
                runs.append(result)
            except Exception as exc:
                failures.append({"error": type(exc).__name__, "time_ns": time.monotonic_ns()})
                break
            # Same observation request cadence ceiling on both systems (5Hz).
            world.stop.wait(0.2)
        world.thread.join()
    finally:
        world.stop.set()
        world.thread.join()
        executor.close()
    admitted = [e for e in world.events if e["kind"] == "admission"]
    summary = {
        "system": system,
        "seed": seed,
        "condition": condition,
        "diagnostic_only": diagnostic,
        "task": "ground-truth joint-space reach, not grasp or semantic quality benchmark",
        "success": world.stable >= 25 and not world.error,
        "workflow_samples": len(runs),
        "failures": failures,
        "physics_error": world.error,
        "wall_s": (world.end - world.begin) / 1e9,
        "sim_s": float(world.data.time),
        "real_time_factor": float(world.data.time) / ((world.end - world.begin) / 1e9),
        "workflow_ms": [(r["end_ns"] - r["start_ns"]) / 1e6 for r in runs],
        "sensor_to_admission_ms": [e["age_ms"] for e in admitted],
        "change_to_fresh_dispatch_ms": None
        if world.change_ns is None or world.fresh_ns is None
        else (world.fresh_ns - world.change_ns) / 1e6,
        "change_to_reach_ms": None
        if world.change_ns is None or world.reached_ns is None
        else (world.reached_ns - world.change_ns) / 1e6,
        "rejections": dict(Counter(e["reason"] for e in world.events if e["kind"] in {"reject", "dispatch_reject"})),
        "admitted_proposals": len(admitted),
        "age_budget_s": 5,
        "deadline_misses": sum((r["end_ns"] - r["start_ns"]) > 5e9 for r in runs),
    }
    summary["no_current_target_fraction"] = world.no_current_target_ticks / max(1, world.control_ticks)
    summary["starvation_definition"] = (
        "fraction of control ticks without an admitted plan for the current scene; previous movement may continue"
    )
    for name, items in [("workflows", runs), ("gate", world.events), ("trajectory", world.frames)]:
        (output / (name + ".jsonl")).write_text("".join(json.dumps(x) + "\n" for x in items))
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "system",
                    "seed",
                    "condition",
                    "success",
                    "workflow_samples",
                    "real_time_factor",
                    "change_to_fresh_dispatch_ms",
                ]
            }
        ),
        flush=True,
    )
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seeds", type=int, default=10)
    p.add_argument(
        "--pairs", type=int, default=None, help="Small pilot: cycle static, early, late conditions across matched pairs"
    )
    p.add_argument("--duration", type=float, default=12)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--diagnostic", action="store_true")
    mode.add_argument("--live", action="store_true")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if not args.diagnostic:
        validate_credentials()
    cells = []
    if args.pairs is not None:
        for i in range(args.pairs):
            c = ["static", "early", "late", "early", "late"][i % 5]
            block = [(s, 101 + i, c) for s in ["A", "B"]]
            random.Random(101 + i).shuffle(block)
            cells += block
    else:
        for seed in range(101, 101 + args.seeds):
            block = [(s, seed, c) for c in ["static", "early", "late"] for s in ["A", "B"]]
            random.Random(seed).shuffle(block)
            cells += block
    config = {
        "cells": cells,
        "duration_s": args.duration,
        "diagnostic": args.diagnostic,
        "task": "joint-space reach",
        "observation_hz": 20,
        "physics_hz": 1000,
        "control_wall_hz": 100,
        "max_observation_age_s": 5,
        "change_times_s": {"static": None, "early": 0.25, "late": 2},
        "success": "max joint error <0.04rad for final 0.25 seconds",
        "scope": "integration pilot; no semantic non-inferiority evidence; no physical hardware",
        "A_model": "gpt-6-astra",
        "A_reasoning": "low",
        "B_model": "jev-1.13.0",
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2))
    import hashlib
    import platform
    import subprocess

    sources = list((ROOT / "scripts").glob("*.py")) + [
        ROOT / "Cargo.lock",
        ROOT / "crates/runtime/src/main.rs",
        ROOT / "workflows/yam_pickup/workflow.json",
    ]
    manifest = {
        "python": sys.version,
        "platform": platform.platform(),
        "mujoco": mujoco.__version__,
        "gap_commit": (ROOT / "gap-commit.txt").read_text().strip(),
        "i2rt_commit": (ROOT / "i2rt-commit.txt").read_text().strip(),
        "source_sha256": {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    import sqlite3

    def spending():
        totals = {}
        for provider in ["astra", "jev"]:
            ledger = Path.home() / f".local/share/rtbench/{provider}-budget.sqlite"
            if ledger.exists():
                with sqlite3.connect(ledger) as db:
                    totals[provider] = {
                        status: {"calls": n, "usd": usd}
                        for status, n, usd in db.execute(
                            "SELECT status,COUNT(*),SUM(charge) FROM calls GROUP BY status"
                        )
                    }
        return totals

    before = spending()
    (args.output / "spending-before.json").write_text(json.dumps(before, indent=2))
    rows = []
    for s, seed, c in cells:
        rows.append(trial(args.output / f"{s}-{seed}-{c}", s, seed, c, args.diagnostic, args.duration))
        (args.output / "summary.json").write_text(json.dumps(rows, indent=2))
        (args.output / "spending-after.json").write_text(json.dumps(spending(), indent=2))


if __name__ == "__main__":
    main()
