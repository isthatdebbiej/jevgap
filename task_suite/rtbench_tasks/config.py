"""Configuration and preflight; loading never imports plugins or contacts a service."""
import copy
import importlib.metadata
import json
import math
import re
import subprocess
from pathlib import Path

from .catalog import TASKS
from .contracts import Scenario

GAP_COMMIT = "c8b5515df80d3029ca5dc7f7f1ec1c327b70bbea"


def gap_revision(path):
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True, timeout=10)
    return result.stdout.strip()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


class Experiment:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.data = read_json(self.path)
        d = self.data
        allowed = {"schema_version", "name", "mode", "tasks", "seeds", "repetitions", "model",
                   "station_config", "scenario_dir", "gap_root", "limits", "harness", "harness_config"}
        if not isinstance(d, dict) or set(d) - allowed:
            raise ValueError("unknown experiment fields")
        if d.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        if not isinstance(d.get("model", {}), dict) or not isinstance(d.get("limits", {}), dict):
            raise ValueError("model and limits must be objects")
        if not isinstance(d.get("name"), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", d["name"]):
            raise ValueError("name must use letters, digits, underscores or hyphens")
        from .upstream import HARNESSES
        self.harness = d.get("harness", "native-gap")
        if self.harness not in HARNESSES:
            raise ValueError(f"harness must be one of {', '.join(HARNESSES)}")
        if d.get("mode") not in {"replay", "se3", "upstream"}:
            raise ValueError("mode must be replay, se3 or upstream")
        if (self.harness == "native-gap") == (d["mode"] == "upstream"):
            raise ValueError("native-gap uses replay/se3; cap, aspire and enpire require mode=upstream")
        self.tasks = list(TASKS) if d.get("tasks") == "all" else d.get("tasks")
        if not isinstance(self.tasks, list) or not self.tasks or any(not isinstance(t, str) or t not in TASKS for t in self.tasks):
            raise ValueError("tasks must be all or a nonempty list of known task ids")
        if len(self.tasks) != len(set(self.tasks)):
            raise ValueError("duplicate task ids")
        seeds = d.get("seeds", [0])
        if not isinstance(seeds, list) or not seeds or any(type(s) is not int or s < 0 for s in seeds) or len(set(seeds)) != len(seeds):
            raise ValueError("seeds must be distinct nonnegative integers")
        repetitions = d.get("repetitions", 1)
        if type(repetitions) is not int or repetitions < 1:
            raise ValueError("repetitions must be a positive integer")
        self.limits = {"max_decisions": 64, "max_age_ms": 2000, "memory_chars": 8000,
                       "episode_timeout_s": 180, "command_timeout_s": 30}
        if set(d.get("limits", {})) - set(self.limits):
            raise ValueError("unknown limits")
        self.limits.update(d.get("limits", {}))
        for k, v in self.limits.items():
            positive(v, k)
        for k in ("max_decisions", "memory_chars"):
            if type(self.limits[k]) is not int:
                raise ValueError(f"{k} must be an integer")
        if len(self.tasks) * len(seeds) * repetitions > 10000:
            raise ValueError("experiment exceeds 10000 trials")
        self.trials = [(t, s, r) for t in self.tasks for s in seeds for r in range(repetitions)]

    def resolve(self, path):
        p = Path(path).expanduser()
        return p.resolve() if p.is_absolute() else (self.path.parent / p).resolve()

    def scenario(self, task, seed, repetition):
        path = self.resolve(self.data["scenario_dir"]) / f"{task}--{seed}--{repetition}.json"
        d = read_json(path)
        for key in ("objects", "targets", "corrections"):
            if key in d:
                d[key] = tuple(d[key])
        s = Scenario(**d)
        if s.task_id != task or s.seed != seed:
            raise ValueError(f"scenario identity mismatch: {path.name}")
        return s

    def model_config(self):
        d = copy.deepcopy(self.data.get("model", {}))
        for name in ("key_file", "budget_ledger"):
            if d.get(name):
                d[name] = str(self.resolve(d[name]))
        return d

    def station_config(self):
        path = self.resolve(self.data["station_config"])
        d = read_json(path)
        allowed = {"station_id", "address", "calibration_id", "start_pose", "driver_factory", "driver_config",
                   "validated_tasks", "press_protocol", "reset_instructions"}
        if not isinstance(d, dict) or set(d) - allowed:
            raise ValueError("unknown station fields; use the saved SE3 login for authentication")
        if not isinstance(d.get("validated_tasks", []), list) or not isinstance(d.get("reset_instructions", {}), dict):
            raise ValueError("invalid station task validation or reset instructions")
        if d.get("driver_config"):
            driver = Path(d["driver_config"]).expanduser()
            d["driver_config"] = str(driver if driver.is_absolute() else (path.parent / driver).resolve())
        return d


def preflight(experiment):
    """Report configuration blockers, never claim a physical capability was tested."""
    e = experiment
    blockers, notes = [], []
    if e.harness != "native-gap":
        from .upstream import preflight_upstream
        blockers, notes = preflight_upstream(e)
        if e.data.get("model") != {"provider": "upstream"}:
            blockers.append("upstream runs require model={provider: upstream}; configure the model in the native workflow")
        blockers.extend(_scenario_blockers(e))
        return _readiness(e, blockers, notes)
    gap = e.data.get("gap_root")
    if not gap or not (e.resolve(gap) / "gap/runtime/executor.py").is_file():
        blockers.append("gap_root must point to the pinned graph-as-policy checkout")
    else:
        try:
            if gap_revision(e.resolve(gap)) != GAP_COMMIT:
                blockers.append(f"graph-as-policy must be pinned to {GAP_COMMIT}")
        except (OSError, subprocess.SubprocessError):
            blockers.append("cannot verify graph-as-policy git revision")
    if e.data["mode"] == "replay":
        notes.append("Replay uses known answers; it is not physics simulation or a model benchmark.")
        if e.data.get("model", {}).get("provider", "replay") != "replay":
            blockers.append("replay mode requires model.provider=replay; live models cannot use answer fixtures")
    else:
        try:
            station = e.station_config()
            for key in ("station_id", "address", "calibration_id", "driver_factory", "driver_config"):
                if not station.get(key) or "REPLACE" in str(station[key]):
                    blockers.append(f"station.{key} is not configured")
            if station.get("driver_factory") and ":" not in station["driver_factory"]:
                blockers.append("driver_factory must be module:factory")
            if station.get("driver_config") and not Path(station["driver_config"]).is_file():
                blockers.append("station.driver_config does not exist")
            if not station.get("start_pose"):
                blockers.append("station.start_pose needs operator-confirmed joint/gripper positions")
            for task in e.tasks:
                if task not in station.get("validated_tasks", []):
                    blockers.append(f"{task}: calibrated driver has not been declared validated")
                if not station.get("reset_instructions", {}).get(task):
                    blockers.append(f"{task}: operator reset instructions are missing")
            if "press-by-number" in e.tasks and station.get("press_protocol") != "two-stage-v1":
                blockers.append("press-by-number: confirm the two-stage-v1 protocol with SE3")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            blockers.append(f"station configuration unavailable ({type(exc).__name__})")
        blockers.extend(_scenario_blockers(e))
        model = e.model_config()
        if model.get("provider") != "openai-responses":
            blockers.append("SE3 runs currently require model.provider=openai-responses")
        else:
            from .responses import validate_config
            try:
                validate_config(model)
                if not Path(model["key_file"]).is_file():
                    blockers.append("model.key_file does not exist")
            except (KeyError, TypeError, ValueError) as exc:
                blockers.append(f"model configuration invalid: {exc}")
        for package in ("se3labs", "se3labs-interface"):
            try:
                if importlib.metadata.version(package) != "0.0.1":
                    blockers.append(f"install {package}==0.0.1")
            except importlib.metadata.PackageNotFoundError:
                blockers.append(f"install {package}==0.0.1")
        notes.append("SE3 login/Tailscale and physical capability are checked at deployment, not by this offline preflight.")
    return _readiness(e, blockers, notes)


def _scenario_blockers(e):
    blockers, identities = [], set()
    for task, seed, repetition in e.trials:
        try:
            s = e.scenario(task, seed, repetition)
            if s.id in identities:
                blockers.append(f"duplicate scenario id: {s.id}")
            identities.add(s.id)
            if s.layout.startswith(("UNCONFIGURED", "fixture", "replay")):
                blockers.append(f"{task}/{seed}/{repetition}: replace the diagnostic layout with a calibrated layout")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            blockers.append(f"{task}/{seed}/{repetition}: scenario unavailable or invalid ({type(exc).__name__})")
    return blockers


def _readiness(e, blockers, notes):
    return {"schema_version": 1, "mode": e.data["mode"], "harness": e.harness, "task_count": len(e.tasks),
            "trial_count": len(e.trials), "configuration_ready": not blockers,
            "hardware_validated": False, "blockers": blockers, "notes": notes}
