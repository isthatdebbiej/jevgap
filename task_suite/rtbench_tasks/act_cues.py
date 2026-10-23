"""Observer-owned cue feed for the precision/memory ACT pilot.

One JSON confirmation file per completed distractor transfer. The policy never
receives the files or hidden scorer state. Observer confirmation is not a
calibrated centre/yaw measurement; SE3 scores the complete episode separately.
"""
import json
from pathlib import Path
from .precision_memory import CueSchedule, DISTRACTOR_TRANSFERS, INITIAL_JOB
from .act_fixture import FixtureGate

ALTERNATE_JOB = INITIAL_JOB.replace("A at T2", "A at T1").replace("C at T1", "C at T3").replace("B at T3", "B at T2")


class CueFeed:
    def __init__(self, directory, episode_id, *, correction=False, variant="delayed"):
        self.directory, self.episode_id = Path(directory), episode_id
        self.schedule = CueSchedule(correction=correction or variant in {"correction","moving-cube"}, initial_job=ALTERNATE_JOB if variant=="different-history" else INITIAL_JOB)
        self.motion_guard = FixtureGate(directory,episode_id) if variant=="moving-cube" else None

    def __call__(self):
        schedule = self.schedule
        if schedule.initial_shown and schedule.transfers < 8:
            index = schedule.transfers+1
            file = self.directory / f"{index}.json"
            if file.exists():
                event = json.loads(file.read_text(encoding="utf-8-sig"))
                obj, target = DISTRACTOR_TRANSFERS[index-1]
                expected = {"episode_id":self.episode_id,"transfer":index,"object":obj,"target":target,"verified":True}
                if event != expected:
                    raise ValueError("cue confirmation has wrong episode, sequence, object or target")
                schedule.verified_transfer(obj, target, verified=True)
        cue = schedule.cue()
        if self.motion_guard and schedule.transfers == 8:
            self.motion_guard.arm()
            if self.motion_guard.refresh() == "waiting":
                return "Wait with the arms stopped for the observer to relocate A and lock the fixture. Do not grasp or move any cube until the new scene is supplied."
        return cue


def confirm(directory, episode_id, transfer, object_id, target_id):
    if type(transfer) is not int or not 1 <= transfer <= 8:
        raise ValueError("transfer must be 1 through 8")
    if (object_id, target_id) != DISTRACTOR_TRANSFERS[transfer-1]:
        raise ValueError("object and target do not match the transfer schedule")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{transfer}.json").open("x", encoding="utf-8") as f:
        json.dump({"episode_id":episode_id,"transfer":transfer,"object":object_id,
                   "target":target_id,"verified":True}, f)


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description="Confirm an independently observed stable D/E transfer; never use a model's self-report.")
    p.add_argument("--directory",required=True)
    p.add_argument("--episode-id",required=True)
    p.add_argument("--transfer",required=True,type=int)
    p.add_argument("--object",required=True)
    p.add_argument("--target",required=True)
    a=p.parse_args(argv)
    confirm(a.directory,a.episode_id,a.transfer,a.object,a.target)


if __name__ == "__main__":
    main()
