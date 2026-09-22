"""Continuous YAM pickup trials; diagnostic runs never count as model results."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import platform
import sys
import threading
import time

import numpy as np
from moving_cube import Pickup, TOP
from executors import Native, Rust, ROOT
from settings import validate_credentials


class LatestSlot:
    """One in-flight request is managed by the caller; one pending observation."""

    def __init__(self):
        self.pending = None
        self.replaced = 0

    def put(self, state):
        if self.pending is not None:
            self.replaced += 1
        self.pending = state

    def take(self):
        state, self.pending = self.pending, None
        return state


def rejection(proposal, observations, version, now, age_ns, ended=False):
    if ended:
        return "ended"
    pv = proposal["source_scene_version"]
    if pv < version:
        return "stale_scene"
    if pv > version:
        return "future_scene"
    record = observations.get(proposal["source_observation_id"])
    if record != (proposal["source_captured_ns"], pv):
        return "unknown_observation"
    if not 0 <= now - proposal["source_captured_ns"] <= age_ns:
        return "expired"
    return None


class ContinuousPickup(Pickup):
    def __init__(self, out, args):
        super().__init__(out)
        self.args = args
        self.slot = LatestSlot()
        self.version = 0
        self.committed = -1
        self.change_ns = None
        self.fresh_ns = None
        self.changed = False
        self.authorized = False
        self.lease_ns = 0
        self.observation_ready_ns = 0
        self.estimate = None
        self.perception = []
        self.paused_ticks = 0
        self.ticks = 0
        self.command_version = None
        self.last_choice = "reperceive"
        self.renderer = None
        self.camera_sample = None
        self.camera_error = None

    def camera_loop(self):
        from types import SimpleNamespace
        import mujoco
        from camera_state import camera_observation

        view = SimpleNamespace(m=self.m, d=mujoco.MjData(self.m), renderer=None)
        try:
            while not self.stop.is_set():
                with self.lock:
                    captured = time.monotonic_ns()
                    version = self.version
                    view.d.qpos[:] = self.d.qpos
                    truth = self.d.xpos[self.cube].copy()
                mujoco.mj_forward(view.m, view.d)
                target, confidence = camera_observation(view)
                ready = time.monotonic_ns()
                with self.lock:
                    self.camera_sample = (captured, ready, version, target, confidence)
                    self.perception.append(
                        {
                            "captured_ns": captured,
                            "ready_ns": ready,
                            "scene_version": version,
                            "estimate": target,
                            "ground_truth_for_scoring": truth.tolist(),
                            "position_error_m": float(np.linalg.norm(np.array(target) - truth))
                            if target is not None
                            else None,
                            "confidence": confidence,
                        }
                    )
                self.stop.wait(max(0, 0.1 - (ready - captured) / 1e9))
        except Exception as exc:
            self.camera_error = type(exc).__name__
        finally:
            if view.renderer is not None:
                view.renderer.close()

    def state(self, now):
        measured = super().state(now)
        truth = measured["target"]
        captured, ready = now, now
        target, confidence = truth, 1.0
        if self.args.perception == "camera":
            sample = self.camera_sample
            target, confidence = None, 0.0
            if sample is not None:
                captured, ready, version, estimate, confidence = sample
                if version == self.version and 0 <= now - captured <= 750_000_000:
                    target = estimate
        else:
            self.perception.append(
                {
                    "captured_ns": now,
                    "ready_ns": now,
                    "scene_version": self.version,
                    "estimate": truth,
                    "ground_truth_for_scoring": truth,
                    "position_error_m": 0.0,
                    "confidence": 1.0,
                }
            )
        self.estimate = target
        self.observation_ready_ns = captured if target is not None else 0
        measured.update(
            captured_ns=captured,
            target=target,
            cube_position_m=target,
            scene_version=self.version,
            committed_scene_version=self.committed,
            perception_source=self.args.perception,
            observation_valid=target is not None,
            confidence=confidence,
            perception_ready_ns=ready,
            observation="Valid target position supplied by the observation source."
            if target is not None
            else "Target occluded, missing or stale; obtain a new observation.",
            task="Pick up the moving cube. Replan authorizes the shared tracker for this scene version. Continue renews an already current plan. Reperceive or abort pauses new tracking commands. A motion-direction change invalidates the current plan.",
            current_plan="Current scene authorized."
            if self.committed == self.version
            else "No valid plan for this scene; replan required if observation is valid.",
        )
        measured.pop("cube_velocity_m_s", None)
        self.observations[self.obsid] = (captured, self.version)
        self.observations = {k: v for k, v in self.observations.items() if now - v[0] <= self.args.age_s * 1e9}
        self.slot.put(measured)
        return measured

    def offer(self, p):
        with self.lock:
            now = time.monotonic_ns()
            reason = rejection(p, self.observations, self.version, now, int(self.args.age_s * 1e9), self.stop.is_set())
            choice = p["decision"]
            if reason is None:
                if choice == "continue" and self.committed != self.version:
                    reason = "no_current_plan"
                elif choice in {"continue", "replan"}:
                    self.committed = self.version
                    self.authorized = True
                    self.lease_ns = now + int(self.args.lease_s * 1e9)
                else:
                    self.authorized = False
                self.last_choice = choice
            self.events.append(
                {
                    "kind": "proposal",
                    "decision": choice,
                    "reason": reason,
                    "gate_ns": now,
                    "wall_s": (now - self.begin) / 1e9,
                    "source_scene_version": p["source_scene_version"],
                    "source_observation_id": p["source_observation_id"],
                    "sensor_to_gate_ms": (now - p["source_captured_ns"]) / 1e6,
                }
            )

    def step(self, t):
        now = time.monotonic_ns()
        if not self.changed and self.args.change_s is not None and self.d.time >= self.args.change_s:
            self.changed = True
            self.version += 1
            self.change_ns = now
            self.authorized = False
            self.command_version = None
            self.drive_speed = -0.008
            self.events.append({"kind": "world_change", "change_ns": now, "wall_s": t, "scene_version": self.version})
        permitted = (
            self.authorized
            and self.committed == self.version
            and now <= self.lease_ns
            and self.estimate is not None
            and 0 <= now - self.observation_ready_ns <= 750_000_000
        )
        self.ticks += 1
        self.paused_ticks += not permitted
        self.accepted = permitted
        if permitted and self.command_version != self.version:
            self.command_version = self.version
            if self.change_ns is not None and self.fresh_ns is None:
                self.fresh_ns = now
            self.events.append(
                {"kind": "controller_dispatch", "dispatch_ns": now, "wall_s": t, "scene_version": self.version}
            )
        # Recheck every physics tick, including commands queued before a scene change.
        super().step(t, target_position=self.estimate, allow_tracking=permitted)

    def run(self, duration, realtime=True, diagnostic=False):
        camera_thread = None
        if self.args.perception == "camera":
            camera_thread = threading.Thread(target=self.camera_loop)
            camera_thread.start()
        try:
            super().run(duration, True, False)
        finally:
            self.stop.set()
            if camera_thread is not None:
                camera_thread.join()


def distribution(values):
    return {
        "n": len(values),
        "p50": float(np.percentile(values, 50)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
    }


def episode(out, system, args):
    world = ContinuousPickup(out, args)
    cfg = {
        "mode": "diagnostic" if args.diagnostic else "live",
        "max_calls": args.max_calls,
        "diagnostic_delay_s": args.worker_delay_s,
        "entrypoint": "astra_provider:decide" if system == "A" else "jev_provider:decide",
    }
    workflow = ROOT / "workflows/yam_pickup/workflow.json"
    runtime = Native(workflow, cfg, out / "native_trace") if system == "A" else Rust(workflow, cfg, out)
    results, failures = [], []
    thread = threading.Thread(target=world.run, args=(args.duration,))
    attempts = 0
    thread.start()
    try:
        while not world.stop.is_set() and attempts < args.max_calls:
            with world.lock:
                state = world.slot.take()
            if state is None:
                world.stop.wait(0.005)
                continue
            attempts += 1
            submitted = time.monotonic_ns()
            try:
                result = runtime.run(state, attempts)
                result.update(
                    submitted_ns=submitted,
                    returned_ns=time.monotonic_ns(),
                    observation_id=state["observation_id"],
                    captured_ns=state["captured_ns"],
                    scene_version=state["scene_version"],
                )
                results.append(result)
                world.offer(result["outputs"]["bench.proposal" if system == "A" else "proposal"]["proposal"])
            except Exception as exc:
                failures.append({"attempt": attempts, "error_type": type(exc).__name__, "at_ns": time.monotonic_ns()})
                # A protocol failure may desynchronize the pool. End inference, keep physics running.
                break
            world.stop.wait(args.decision_interval_s)
        thread.join()
    finally:
        world.stop.set()
        thread.join()
        runtime.close()
    gates = [e for e in world.events if e["kind"] == "proposal"]
    worker_events = [e for r in results for e in r["events"]]
    inference = []
    for r in results:
        p = r["outputs"]["bench.proposal" if system == "A" else "proposal"]["proposal"]
        inference.append((p["decision_ready_ns"] - p["request_start_ns"]) / 1e6)
    summary = {
        "system": system,
        "diagnostic": args.diagnostic,
        "perception": args.perception,
        "success": bool(world.success_s is not None and world.contacts() and world.d.xpos[world.cube, 2] > TOP + 0.05),
        "success_s": world.success_s,
        "pickup_s": world.pickup_s,
        "physics_s": float(world.d.time),
        "wall_s": (world.end - world.begin) / 1e9,
        "real_time_factor": float(world.d.time) / ((world.end - world.begin) / 1e9),
        "attempts": attempts,
        "completed_workflows": len(results),
        "failures": failures,
        "physics_error": world.error,
        "camera_error": world.camera_error,
        "replaced_pending_observations": world.slot.replaced,
        "pending_at_end": int(world.slot.pending is not None),
        "call_limit_reached": attempts >= args.max_calls,
        "gate_rejections": dict(Counter(e["reason"] for e in gates if e["reason"])),
        "paused_tick_fraction": world.paused_ticks / max(world.ticks, 1),
        "change_to_fresh_dispatch_ms": (world.fresh_ns - world.change_ns) / 1e6 if world.fresh_ns else None,
        "change_without_fresh_dispatch": world.change_ns is not None and world.fresh_ns is None,
        "workflow_ms": distribution([(r["returned_ns"] - r["submitted_ns"]) / 1e6 for r in results]),
        "decision_worker_ms": distribution(inference),
        "worker_service_ms": distribution([(e["worker_end_ns"] - e["worker_start_ns"]) / 1e6 for e in worker_events]),
        "dispatch_to_worker_ms": distribution(
            [(e["worker_start_ns"] - e["dispatch_ns"]) / 1e6 for e in worker_events if "dispatch_ns" in e]
        ),
        "worker_to_result_receipt_ms": distribution(
            [(e["received_ns"] - e["worker_end_ns"]) / 1e6 for e in worker_events if "received_ns" in e]
        ),
        "observation_to_submission_ms": distribution([(r["submitted_ns"] - r["captured_ns"]) / 1e6 for r in results]),
        "eligible_to_start_ms": distribution(
            [(e["worker_start_ns"] - e["eligible_ns"]) / 1e6 for e in worker_events if "eligible_ns" in e]
        ),
        "sensor_to_gate_ms": distribution([e["sensor_to_gate_ms"] for e in gates if e["reason"] is None]),
        "perception_ms": distribution([(e["ready_ns"] - e["captured_ns"]) / 1e6 for e in world.perception]),
        "perception_position_error_m": distribution(
            [e["position_error_m"] for e in world.perception if e["position_error_m"] is not None]
        ),
        "missing_perception_frames": sum(e["estimate"] is None for e in world.perception),
        "change_detection": "scripted simulator direction-change event; not a camera motion-change detector",
    }
    for name, rows in [
        ("trajectory", world.frames),
        ("events", world.events),
        ("workflows", results),
        ("perception", world.perception),
    ]:
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--diagnostic", action="store_true")
    mode.add_argument("--live", action="store_true")
    p.add_argument("--perception", choices=["ground-truth", "camera"], default="ground-truth")
    p.add_argument("--pairs", type=int, default=3)
    p.add_argument("--duration", type=float, default=12)
    p.add_argument("--change-s", type=float, default=1.0)
    p.add_argument("--age-s", type=float, default=5)
    p.add_argument("--lease-s", type=float, default=5)
    p.add_argument("--worker-delay-s", type=float, default=0.15)
    p.add_argument("--decision-interval-s", type=float, default=0.2)
    p.add_argument("--max-calls", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    if (
        min(a.pairs, a.duration, a.age_s, a.lease_s, a.max_calls) <= 0
        or min(a.worker_delay_s, a.decision_interval_s) < 0
        or not 0 < a.change_s < a.duration
    ):
        p.error("Invalid count, duration, budget or change time")
    if a.live:
        validate_credentials()
    a.output.mkdir(parents=True, exist_ok=False)
    order = []
    for pair in range(a.pairs):
        order.extend([(pair, s) for s in (["A", "B"] if pair % 2 == 0 else ["B", "A"])])
    random.Random(a.seed).shuffle(order)  # Paired scene parameters; randomized collection order.
    config = {k: v for k, v in vars(a).items() if k != "output"}
    config.update(
        order=order,
        environment={
            "python": sys.version.split()[0],
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "numpy": np.__version__,
        },
        source_sha256={
            f: hashlib.sha256((ROOT / "scripts" / f).read_bytes()).hexdigest()
            for f in ["continuous.py", "moving_cube.py", "executors.py", "camera_state.py"]
        },
    )
    (a.output / "config.json").write_text(json.dumps(config, indent=2))
    summaries = [dict(pair=pair, **episode(a.output / f"pair-{pair}" / system, system, a)) for pair, system in order]
    (a.output / "summary.json").write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
