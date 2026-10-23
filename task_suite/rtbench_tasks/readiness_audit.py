"""Evidence-based readiness matrix; never contacts a model or robot."""
import argparse
import copy
import json
import hashlib
from pathlib import Path

from .catalog import TASKS
from .config import Experiment, preflight


# The linked SE3 proposal differs from the original simulation contracts.
ADAPTATIONS = {
    "stack-blocks": "Not in the linked ten-task proposal; freeze its separate physical rubric.",
    "stack-bowls": "Not in the linked ten-task proposal; freeze its separate physical rubric.",
    "arrange-largest-number": "Not in the linked ten-task proposal; freeze digit identities and ordering rubric.",
    "pack-objects-into-box": "Define fronts of the car, shoe, toothbrush and hammer; measure containment.",
    "hang-mugs": "Local contract expects three mugs; linked physical proposal has two.",
    "cover-blocks": "Local red/green/blue recall differs from physical green/light-blue/dark-blue materials.",
    "press-by-number": "Freeze button roles, card counts and one-confirm versus two-stage confirmation protocol.",
    "plug-in-charger": "Record target socket and insertion criteria; physical strip must be disconnected and de-energized.",
    "insert-tubes": "Local contract expects three tubes; linked physical proposal has two marked target wells.",
    "classify-objects": "Freeze taxonomy and inventory for writing tools, toy vehicle and camera equipment.",
    "play-stacking-toy": "Local contract has four pegs/ten pieces; linked physical proposal has five pegs/fifteen pieces.",
    "align-blocks": "Local contract uses a set square; linked proposal uses a metal ruler and requires an alignment tolerance.",
    "classify-objects-by-language": "Freeze category-to-bin mapping and randomized assignments for peppers, figurines and watches.",
}


def audit(gap_config, cap_config, *, station_id="se3-labs-yam-2", address="100.107.161.92:7443"):
    profiles = {"native-gap": Experiment(gap_config), "cap": Experiment(cap_config)}
    result = {"all_tasks_runnable": False, "hardware_tests_performed": False,
              "requested_bridge": "xpolicylab", "station_id": station_id,
              "episode_limit_s": 450, "tasks": [],
              "audit_scope": "Current implementation snapshot; repeat source review after integration changes",
              "source_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ("experiment.py", "upstream_worker.py", "xpolicylab.py", "precision_memory.py")}}
    for task in TASKS:
        row = {"task_id": task, "contract_implemented": True,
               "task_specific_work": ADAPTATIONS[task], "harnesses": {}}
        for harness, original in profiles.items():
            e = copy.deepcopy(original)
            e.tasks = [task]
            e.trials = [trial for trial in original.trials if trial[0] == task]
            check = preflight(e)
            blockers = list(check["blockers"])
            if not e.trials:
                blockers.append("task is not selected in this profile")
            if e.limits["episode_timeout_s"] != 450:
                blockers.append("profile does not use the agreed 450-second limit")
            try:
                station = e.station_config()
                if (station.get("station_id"), station.get("address")) != (station_id, address):
                    blockers.append("profile targets a different station/address")
            except (OSError, KeyError, ValueError, TypeError):
                blockers.append("station profile is unavailable")
            # Source-level fact: experiment._run_se3 uses serve_policy; the CaP
            # worker's sole shared physical adapter is cap_act, not XPolicyLab.
            blockers.append("native deployment is not wired to the XPolicyLab runner")
            blockers.append("physical task adaptation and scoring have not been commissioned")
            row["harnesses"][harness] = {"runnable": False, "blockers": blockers}
        result["tasks"].append(row)
    result["tasks"].append({
        "task_id": "precision-memory", "contract_implemented": False,
        "protocol_implemented": True, "runnable": False,
        "blockers": [
            "cue protocol and SDK scoring sheet exist, but neither native deployment consumes them",
            "the thirteen-task action schema cannot express numeric yaw targets",
            "verified transfer events, instruction hiding and per-episode memory isolation need end-to-end integration",
            "same-scene alternate-history and moving-cube variants are not implemented",
            "layout, yaw reference, placement tolerances and independent measurements must be frozen",
        ],
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-config", required=True)
    parser.add_argument("--cap-config", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.gap_config, args.cap_config)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(f"Audited {len(result['tasks'])} task definitions; all_tasks_runnable=false")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
