"""Move-stop-pick fixture handshake, with explicit observer confirmation.

After the final decision observation, the first proposed motion is withheld.
The controller holds. An observer checks clearance, relocates A, locks the
fixture, then confirms. No saved pre-move command is replayed.
"""
import json
import math
import uuid
from pathlib import Path


class FixtureGate:
    def __init__(self, directory, episode_id):
        self.directory, self.episode_id = Path(directory), episode_id
        self.stage, self.token, self.observed_token = "unarmed", None, None
        self.after_station_s = None

    def arm(self):
        if self.stage == "unarmed": self.stage = "armed"

    def refresh(self):
        file=self.directory/"fixture-locked.json"
        if self.stage == "waiting" and file.exists():
            event=json.loads(file.read_text(encoding="utf-8-sig"))
            if (set(event)!={"episode_id","request_token","arm_clear","locked","after_station_s"}
                    or event["episode_id"]!=self.episode_id or event["request_token"]!=self.token
                    or event["arm_clear"] is not True or event["locked"] is not True):
                raise ValueError("invalid fixture confirmation")
            stamp=event["after_station_s"]
            if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):
                raise ValueError("invalid fixture station timestamp")
            self.after_station_s, self.stage=stamp,"locked"
        return self.stage

    def observed(self, oldest_camera_timestamp):
        self.refresh()
        if self.stage == "locked":
            if oldest_camera_timestamp <= self.after_station_s:
                raise ValueError("camera frames predate the locked fixture")
            self.observed_token=self.token

    def before_motion(self, robot, name, arguments):
        self.refresh()
        if self.stage == "unarmed": return None
        if self.stage == "armed":
            self.token=uuid.uuid4().hex
            hold=robot.harness.hold()
            robot.journal({"kind":"fixture_hold","reply":hold})
            if not hold.get("ok"):
                raise RuntimeError("fixture hold request failed")
            self.directory.mkdir(parents=True,exist_ok=True)
            with (self.directory/"fixture-request.json").open("x",encoding="utf-8") as f:
                json.dump({"episode_id":self.episode_id,"request_token":self.token,
                           "withheld_tool":name,"withheld_arguments":arguments},f,indent=2)
            self.stage="waiting"
        if self.stage == "waiting" or self.observed_token != self.token:
            return {"ok":False,"command_executed":False,"refresh_observation":True,
                    "message":"Motion withheld for the fixture transition. Keep holding. An independent observer must confirm A was relocated with arms clear and the fixture locked. Then observe the new scene and make a new decision."}
        return None


def confirm(directory, harness, *, arm_clear, locked):
    if arm_clear is not True or locked is not True:
        raise ValueError("observer must verify clearance and fixture lock")
    directory=Path(directory)
    request=json.loads((directory/"fixture-request.json").read_text())
    status=harness.status()
    if not status.get("ok") or status.get("phase")!="rollout" or status.get("episode_id")!=request["episode_id"]:
        raise ValueError("fixture request does not match the live episode")
    stamps=[a.get("measured_timestamp_s") for a in status["arms"].values()]
    if not stamps or any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) for t in stamps):
        raise ValueError("missing measured station time")
    event={"episode_id":request["episode_id"],"request_token":request["request_token"],
           "arm_clear":True,"locked":True,"after_station_s":max(stamps)}
    with (directory/"fixture-locked.json").open("x",encoding="utf-8") as f:
        json.dump(event,f,indent=2)


def main(argv=None):
    import argparse
    from se3labs.sdk.examples.act_harness.tools import Harness
    p=argparse.ArgumentParser(description="Confirm the prescribed A-cube relocation only after the arm is clear and the fixture locked.")
    p.add_argument("--directory",required=True)
    p.add_argument("--socket",required=True)
    p.add_argument("--arm-clear",action="store_true",required=True)
    p.add_argument("--locked",action="store_true",required=True)
    a=p.parse_args(argv)
    confirm(a.directory,Harness(a.socket),arm_clear=a.arm_clear,locked=a.locked)


if __name__ == "__main__": main()
