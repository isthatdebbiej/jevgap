"""Model-facing ACT tools shared by native GaP and CaP. Operator-scored.

Uses SE3's documented controller, not a semantic grasp/place driver. Motion
completion is feedback, never proof of a grasp or successful task.
"""
import base64
import copy
import hashlib
import io
import json
import math
import time
from pathlib import Path
from PIL import Image
from se3labs.sdk.examples.act_harness.tools import TOOLS, call_tool

NAMES = {"robot_status", "robot_move", "robot_goto", "robot_rotate",
         "robot_gripper", "robot_hold", "robot_end_episode"}
DEFINITIONS = [copy.deepcopy(t) for t in TOOLS if t["name"] in NAMES]
INSTRUCTIONS = (
    "Use ACT tools to solve the task from camera images. Translations are metres "
    "in EACH ARM's base frame: X forward, Y left, Z up. Rotations are degrees "
    "around base axes. Goto offsets are relative to episode start, not the table. "
    "Gripper 0 is closed, 1 open. Inspect observations after movements. ok=true "
    "does not prove a grasp, placement or task success. The controller has IK "
    "and reach checks, but no table/collision model or lower-Z bound. Use small "
    "visual corrections; do not treat inferred depth as certain. Request "
    "robot_end_episode when done or unable to proceed. The operator scores. "
    "Use only documented robot tools, not Python system/file/network access."
)


class Robot:
    def __init__(self, harness, output, *, max_commands=128, max_age_s=2):
        self.harness, self.output = harness, Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.max_commands, self.max_age_s = max_commands, max_age_s
        self.ended, self.calls = False, 0
        self.episode_id = self.deadline = None
        self.motion_guard = None
        self.events = []

    def journal(self, event):
        self.events.append(event)
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, allow_nan=False)+"\n")

    def status(self):
        if self.ended:
            raise RuntimeError("episode ended")
        status = self.harness.status()
        if not status.get("ok") or status.get("phase") != "rollout":
            raise RuntimeError("ACT is not in a live rollout")
        identity = status.get("episode_id")
        if not identity:
            raise ValueError("use the single-episode ACT agent service")
        if self.episode_id is None:
            self.episode_id = identity
        if identity != self.episode_id:
            raise RuntimeError("ACT episode changed")
        elapsed, budget = status.get("elapsed_s"), status.get("budget_s")
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in (elapsed, budget)):
            raise ValueError("missing rollout timer")
        if not 0 <= elapsed < budget <= 450:
            raise TimeoutError("rollout time limit")
        candidate = time.monotonic()+budget-elapsed
        self.deadline = candidate if self.deadline is None else min(self.deadline, candidate)
        if time.monotonic() >= self.deadline:
            raise TimeoutError("rollout deadline")
        received = status.get("observation_received_ns")
        age = (time.monotonic_ns()-received)/1e9 if type(received) is int else math.inf
        if not 0 <= age <= self.max_age_s:
            raise TimeoutError("stale ACT telemetry")
        return status

    def observe(self):
        if self.motion_guard and self.motion_guard.refresh() == "locked":
            wait_until = time.monotonic()+self.max_age_s
            while True:
                self.status()
                frames=self.harness.cameras().get("cameras",{})
                stamps=[frames.get(name,{}).get("timestamp",-float("inf")) for name in ("topdown","wrist_left","wrist_right")]
                if min(stamps)>self.motion_guard.after_station_s: break
                if time.monotonic()>=wait_until: raise TimeoutError("post-fixture camera frames unavailable")
                time.sleep(0.05)
        status = self.status()
        reply = self.harness.cameras()
        if not reply.get("ok") or reply.get("episode_id") != self.episode_id:
            raise RuntimeError("camera capture unavailable or wrong episode")
        content, records = [], []
        cameras = reply.get("cameras", {})
        if not {"topdown", "wrist_left", "wrist_right"}.issubset(cameras):
            raise ValueError("all three station cameras are required")
        stamps = [a.get("measured_timestamp_s") for a in status["arms"].values()]
        if not stamps or any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in stamps):
            raise ValueError("missing arm timestamps")
        latest = max(stamps)
        if latest-min(stamps) > self.max_age_s:
            raise TimeoutError("unsynchronized arms")
        folder = self.output / f"observation-{len(self.events):04d}"
        folder.mkdir(exist_ok=False)
        for name in ("topdown", "wrist_left", "wrist_right"):
            entry = cameras[name]
            stamp = entry.get("timestamp")
            if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or abs(latest-stamp) > self.max_age_s:
                raise TimeoutError("stale camera")
            data = Path(entry["path"]).read_bytes()
            if len(data) > 10*1024*1024:
                raise ValueError("oversized frame")
            path = folder / (name+".jpg")
            path.write_bytes(data)
            with Image.open(io.BytesIO(data)) as image:
                image = image.convert("RGB")
                image.thumbnail((320, 180))
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=65)
            content.extend([{"type":"text", "text":name}, {"type":"image_url", "image_url":{
                "url":"data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()}}])
            records.append({"camera":name,"timestamp":stamp,"path":str(path),"sha256":hashlib.sha256(data).hexdigest()})
        if self.motion_guard:
            self.motion_guard.observed(min(r["timestamp"] for r in records))
        public = {k: status[k] for k in ("elapsed_s", "budget_s", "arms", "episode_id")}
        self.journal({"kind":"observation","state":public,"frames":records})
        return public, content

    def call(self, name, arguments=None):
        arguments = {} if arguments is None else arguments
        if name not in NAMES or not isinstance(arguments, dict):
            raise ValueError("unsupported ACT tool")
        schema = next(t for t in DEFINITIONS if t["name"] == name)["parameters"]
        if set(arguments)-set(schema["properties"]) or set(schema["required"])-set(arguments):
            raise ValueError("invalid tool arguments")
        if "arm" in arguments and arguments["arm"] not in {"left", "right"}:
            raise ValueError("invalid arm")
        for k, v in arguments.items():
            if k == "arm" or (k == "position" and v in ("open", "close")):
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError("tool numbers must be finite")
        if "position" in arguments and isinstance(arguments["position"], (int, float)) and not 0 <= arguments["position"] <= 1:
            raise ValueError("gripper fraction out of range")
        status = self.status()
        if self.calls >= self.max_commands:
            raise RuntimeError("command budget exhausted")
        if name in {"robot_move", "robot_goto"}:
            delta = ([arguments.get(k, 0) for k in ("dx", "dy", "dz")] if name == "robot_move" else
                     [arguments[k]-status["arms"][arguments["arm"]]["offset_m"][i] for i,k in enumerate(("x","y","z"))])
            if math.sqrt(sum(v*v for v in delta)) > 0.05+1e-9:
                raise ValueError("translation exceeds 5 cm per command")
        angles = [arguments.get(k, 0) for k in ("roll", "pitch", "yaw")]
        if name == "robot_goto":
            current = status["arms"][arguments["arm"]]["rpy_deg"]
            angles = [((v-current[i]+180)%360)-180 for i,v in enumerate(angles)]
        if any(abs(v) > 30 for v in angles):
            raise ValueError("rotation exceeds 30 degrees per command")
        if self.motion_guard and name in {"robot_move","robot_goto","robot_rotate","robot_gripper"}:
            refusal = self.motion_guard.before_motion(self,name,arguments)
            if refusal is not None:
                self.journal({"kind":"withheld_motion","name":name,"arguments":arguments,"reply":refusal})
                return refusal
        self.harness.timeout_s = min(30, max(0.1, self.deadline-time.monotonic()))
        self.calls += 1
        reply = call_tool(self.harness, name, arguments)
        self.journal({"kind":"tool","name":name,"arguments":arguments,"reply":reply})
        if name == "robot_end_episode":
            self.ended = True
        if not reply.get("ok"):
            self.ended = True
            self.harness.hold()
            self.harness.end_episode()
            raise RuntimeError("ACT tool failed; uncertain physical actions are not retried")
        return reply

    def stop(self):
        if not self.ended:
            try:
                self.harness.timeout_s = 2
                self.journal({"kind":"cleanup_hold", "reply":self.harness.hold()})
            finally:
                try:
                    self.journal({"kind":"cleanup_end", "reply":self.harness.end_episode()})
                finally:
                    self.ended = True


def prompt(robot, instruction, memory="", *, code=False, graph=False):
    state, images = robot.observe()
    instruction = instruction() if callable(instruction) else instruction
    output = ("Return a Python code block using robot.call(name, arguments). "
              "Use only one motion per block, then inspect the next observation."
              if code else 'Return only JSON with exactly tool (name), arguments (object), memory (string).')
    if graph:
        output = "Author an executable ACT action graph using the graph contract below."
    text = INSTRUCTIONS+"\n"+output+"\n"+json.dumps({"instruction":instruction,
           "memory":memory,"state":state,"tools":DEFINITIONS}, allow_nan=False)
    return [{"role":"user", "content":[{"type":"text","text":text}, *images]}]
