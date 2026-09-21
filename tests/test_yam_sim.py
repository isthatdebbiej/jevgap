import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from yam_sim import World
from executors import compile_workflow, ROOT


def world():
    w = World.__new__(World)
    w.model = SimpleNamespace(jnt_range=np.array([[-3, 3]] * 6))
    w.scene_version = 1
    w.captured = {8: (100, 1), 7: (90, 0)}
    w.age_ns = 1000
    w.lock = threading.RLock()
    w.stop = threading.Event()
    w.pending = None
    w.events = []
    return w


def proposal():
    return {
        "source_observation_id": 8,
        "source_scene_version": 1,
        "source_captured_ns": 100,
        "decision": "replan",
        "target": [0] * 6,
    }


def test_gate_fresh_stale_future_expired():
    w = world()
    p = proposal()
    assert w.validate(p, 101) is None
    assert w.validate(p, 1101) == "expired"
    assert w.validate(p, 99) == "expired"
    for version, reason in [(0, "stale_scene"), (2, "unknown_future_scene")]:
        assert w.validate(dict(p, source_scene_version=version), 101) == reason
    assert w.validate(dict(p, source_observation_id=999), 101) == "unknown_observation"


def test_queued_proposal_rechecked_after_change():
    w = world()
    p = proposal()
    assert w.validate(p, 101) is None
    with w.lock:
        w.scene_version = 2
    assert w.validate(p, 102) == "stale_scene"


def test_invalid_actions():
    w = world()
    p = proposal()
    for target in [[float("nan")] * 6, [4] * 6, []]:
        assert w.validate(dict(p, target=target), 101) is not None
    assert w.validate(dict(p, decision="move_arm"), 101) == "invalid_decision"


@pytest.mark.parametrize("mutation", ["actuator", "loop", "conditional", "stream", "subgraph"])
def test_importer_rejects_unsupported(tmp_path, mutation):
    g = json.loads((ROOT / "workflows/yam_pickup/workflow.json").read_text())
    if mutation == "actuator":
        g["nodes"]["state"]["tool"] = "robot.move"
    elif mutation == "loop":
        g["edges"].append(["proposal", "state"])
    elif mutation == "conditional":
        g["conditional_edges"] = {"state": {}}
    elif mutation == "stream":
        g["nodes"]["state"]["streaming"] = True
    else:
        g["subgraphs"] = {"nested": {}}
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(g))
    with pytest.raises(ValueError):
        compile_workflow(path)
