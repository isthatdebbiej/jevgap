"""Launch pinned upstream workflows; never substitute a local algorithm."""
import hashlib
import json
import math
import os
import signal
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from .catalog import TASKS
from .config import gap_revision, positive, read_json
from .contracts import Evidence
from .scoring import evaluate

UPSTREAMS = {
    "cap": {"name": "CaP-X", "url": "https://github.com/capgym/cap-x",
            "revision": "53e9966d7a8e2fa7494676772bccc35280f5c0ed",
            "entry": "capx/envs/launch.py", "cwd": "."},
    "aspire": {"name": "ASPIRE saved-policy runner", "url": "https://github.com/NVlabs/ASPIRE",
               "revision": "f4c8939aab0af9b97690c561bd80e282940f7886",
               "entry": "aspire/real/run_script.py", "cwd": "aspire/real"},
    "enpire": {"name": "ENPIRE TrialRunner", "url": "https://github.com/NVlabs/ENPIRE",
               "revision": "99ee90acf65b5b18957c8382ad580db999528be3",
               "entry": "enpire/env/forge/loop.py", "cwd": "."},
}
HARNESSES = ("native-gap", *UPSTREAMS)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_profile(experiment):
    path = experiment.resolve(experiment.data["harness_config"])
    data = read_json(path)
    allowed = {"schema_version", "repo_root", "revision", "python", "timeout_s", "task_config_pattern", "evaluation_backend"}
    if not isinstance(data, dict) or set(data) - allowed or data.get("schema_version") != 1:
        raise ValueError("invalid upstream profile fields or schema_version")
    positive(data.get("timeout_s", 600), "upstream.timeout_s")
    if data.get("evaluation_backend") not in {"se3", "simulation"}:
        raise ValueError("upstream.evaluation_backend must be se3 or simulation")
    for name in ("repo_root", "python"):
        raw = data.get(name, "")
        if not isinstance(raw, str) or not raw or "REPLACE" in raw:
            raise ValueError(f"configure upstream.{name}")
        value = Path(raw).expanduser()
        data[name] = str(value.resolve() if value.is_absolute() else (path.parent / value).resolve())
    if not isinstance(data.get("revision"), str) or len(data["revision"]) != 40 or any(c not in "0123456789abcdef" for c in data["revision"]):
        raise ValueError("upstream.revision must be a full lowercase commit SHA")
    if not isinstance(data.get("task_config_pattern"), str) or not data["task_config_pattern"]:
        raise ValueError("configure upstream.task_config_pattern")
    return path, data


def task_binding(profile_path, profile, task, seed, repetition):
    rendered = profile["task_config_pattern"].format(task=task, seed=seed, repetition=repetition)
    path = Path(rendered).expanduser()
    path = path.resolve() if path.is_absolute() else (profile_path.parent / path).resolve()
    binding = read_json(path)
    if not isinstance(binding, dict) or binding.get("configured") is not True:
        raise ValueError("native task binding is not configured")
    if (type(binding.get("seed")) is not int or type(binding.get("repetition")) is not int
            or (binding.get("task_id"), binding.get("seed"), binding.get("repetition")) != (task, seed, repetition)):
        raise ValueError("native task binding identity differs from experiment")
    return path, binding


def _binding_paths(path, binding, harness):
    common = {"configured", "task_id", "seed", "repetition", "args"}
    specific = {"cap": {"config_file"}, "aspire": {"program_file"},
                "enpire": {"environment_factory", "policy_factory", "environment_kwargs", "policy_kwargs", "max_steps"}}
    if set(binding) - common - specific[harness]:
        raise ValueError("unknown native task binding fields")
    required = {"cap": ("config_file",), "aspire": ("program_file",), "enpire": ()}[harness]
    for key in required:
        raw = binding.get(key, "")
        if not isinstance(raw, str) or not raw:
            raise ValueError(f"native task binding requires {key}")
        p = Path(raw).expanduser()
        p = p if p.is_absolute() else path.parent / p
        if not p.is_file():
            raise ValueError(f"native {key} does not exist")
    args = binding.get("args", [])
    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise ValueError("native args must be a list of strings")
    # Output destinations and the one-trial mapping are owned by this adapter.
    reserved = ("--output-dir", "--total-trials", "--num-workers", "--config-path", "--web-ui",
                "script_file=", "script_output_dir=", "env.seed=", "hydra.run.dir=")
    if any(a.lstrip("+").replace("_", "-").startswith(tuple(r.replace("_", "-") for r in reserved)) for a in args):
        raise ValueError("native args override an adapter-owned task/output setting")
    if any("api_key" in a.lower() or "api-key" in a.lower() or "sk-" in a for a in args):
        raise ValueError("use upstream credential files or its authenticated model server, not inline API keys")
    if harness == "enpire":
        if args:
            raise ValueError("ENPIRE TrialRunner uses factory kwargs, not CLI args")
        for key in ("environment_factory", "policy_factory"):
            if not isinstance(binding.get(key), str) or ":" not in binding[key]:
                raise ValueError(f"native task binding requires {key}=module:callable")
        if not isinstance(binding.get("environment_kwargs", {}), dict) or not isinstance(binding.get("policy_kwargs", {}), dict):
            raise ValueError("ENPIRE factory kwargs must be objects")
        if type(binding.get("max_steps", 64)) is not int or binding.get("max_steps", 64) <= 0:
            raise ValueError("ENPIRE max_steps must be a positive integer")


def preflight_upstream(experiment):
    e = experiment
    blockers = []
    harness = e.harness
    if harness not in UPSTREAMS:
        return ["mode=upstream requires cap, aspire or enpire"], []
    notes = [f"Uses {UPSTREAMS[harness]['name']} in its own Python environment; no algorithm emulation.",
             "Upstream model settings/budgets are owned by its native config, not the native GaP Responses adapter.",
             "Independent evidence.json is required for a comparable local task score; native success alone cannot pass.",
             "Task bindings must adapt the native environment to the prescribed layout and SE3 transport where applicable."]
    if os.name == "nt" and harness in {"cap", "aspire"}:
        blockers.append(f"{harness} native runtime requires Linux; run this suite inside Linux/WSL with Linux paths and interpreters")
    try:
        path, profile = load_profile(e)
        root = Path(profile["repo_root"])
        if not Path(profile["python"]).is_file():
            blockers.append("upstream.python executable does not exist")
        if not (root / UPSTREAMS[harness]["entry"]).is_file():
            blockers.append(f"upstream checkout lacks {UPSTREAMS[harness]['entry']}")
        try:
            if gap_revision(root) != profile["revision"]:
                blockers.append("upstream checkout differs from the configured revision")
            dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                                   capture_output=True, text=True, check=True, timeout=10).stdout
            if dirty.strip():
                blockers.append("upstream tracked sources have uncommitted changes; commit and pin the adaptation")
        except (OSError, subprocess.SubprocessError):
            blockers.append("cannot verify upstream git revision")
        if harness == "aspire":
            for missing in ("cap/agent/robot_adapters.py", "cap/agent/script_backends.py", "cap/agent/recorder.py"):
                module = root / UPSTREAMS[harness]["cwd"] / missing
                if not module.is_file() and not module.with_suffix("").is_dir():
                    blockers.append(f"ASPIRE workstation recovery required: {missing}")
        for task, seed, repetition in e.trials:
            try:
                binding_path, binding = task_binding(path, profile, task, seed, repetition)
                _binding_paths(binding_path, binding, harness)
            except (OSError, KeyError, ValueError, TypeError) as exc:
                blockers.append(f"{task}/{seed}/{repetition}: {exc}")
    except (KeyError, OSError, ValueError, TypeError) as exc:
        blockers.append(f"upstream configuration unavailable: {exc}")
    return blockers, notes


def write_templates(root, base_config):
    from .experiment import write_json
    for harness, upstream in UPSTREAMS.items():
        config = {**base_config, "mode": "upstream", "harness": harness,
                  "name": f"{harness}-13-tasks", "harness_config": f"upstream/{harness}.local.json",
                  "model": {"provider": "upstream"}}
        write_json(root / f"{harness}.local.json", config)
        write_json(root / "upstream" / f"{harness}.local.json", {
            "schema_version": 1, "repo_root": "REPLACE-upstream-checkout", "revision": upstream["revision"],
            "python": "REPLACE-upstream-python-executable", "timeout_s": 600, "evaluation_backend": "se3",
            "task_config_pattern": f"{harness}/{{task}}--{{seed}}--{{repetition}}.json"})
        for task in TASKS:
            binding = {"configured": False, "task_id": task, "seed": 0, "repetition": 0, "args": []}
            if harness == "cap":
                binding["config_file"] = ""
            elif harness == "aspire":
                binding["program_file"] = ""
            else:
                binding.update(environment_factory="", policy_factory="", environment_kwargs={}, policy_kwargs={}, max_steps=64)
            write_json(root / "upstream" / harness / f"{task}--0--0.json", binding)


def _terminate(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def normalize(folder, scenario, harness, returncode, evaluation_backend):
    """Native success is kept separate from the common independent evaluator."""
    raw = read_json(folder / "upstream-result.json")
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or raw.get("harness") != harness or raw.get("episode_id") != scenario.id:
        raise ValueError("upstream result identity mismatch")
    if type(raw.get("execution_ok")) is not bool or type(raw.get("native_success")) is not bool:
        raise ValueError("upstream result requires boolean execution_ok and native_success")
    score = raw.get("native_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise ValueError("upstream native_score must be finite")
    evidence_file = folder / "evidence.json"
    result = {"status": "error", "task_success": False, "upstream_success": raw["native_success"],
              "upstream_score": score, "score_source": "upstream-native", "ranking_eligible": False,
              "evaluation_backend": evaluation_backend}
    if returncode != 0 or not raw["execution_ok"]:
        result["error_type"] = "upstream_execution_failed"
        return result
    if not evidence_file.is_file():
        result["error_type"] = "missing_independent_evidence"
        return result
    evidence_data = read_json(evidence_file)
    evidence_data["events"] = tuple(evidence_data.get("events", []))
    local = evaluate(scenario, Evidence(**evidence_data))
    result.update(local_score=asdict(local), score_source="independent-local-rubric")
    operator_success = True
    if evaluation_backend == "se3":
        session_path = folder / "se3-session.json"
        if not session_path.is_file():
            result["error_type"] = "missing_se3_session"
            return result
        session = read_json(session_path)
        scores = session.get("results", [])
        scored = isinstance(scores, list) and len(scores) == 1 and scores[0].get("scored") is True
        ok = (session.get("episode_id") == scenario.id and session.get("state") == "SUCCEEDED"
              and session.get("episodes") == 1 and session.get("error_count") == 0
              and session.get("bridge_error") is None and scored)
        operator_success = bool(scored and scores[0].get("success") is True)
        result.update(operator_scored=bool(scored), operator_success=operator_success)
        if not ok:
            result["error_type"] = "se3_session_failed_or_unscored"
            return result
    elif evaluation_backend != "simulation":
        raise ValueError("unknown evaluation backend")
    result.update(status="completed", task_success=bool(raw["native_success"] and local.success and operator_success))
    return result


def run_trial(experiment, task, seed, repetition, folder, *, live=False):
    from .experiment import write_json
    if not live:
        raise ValueError("upstream processes require --live; native runners can spend credits or move hardware")
    e = experiment
    path, profile = load_profile(e)
    binding_path, binding = task_binding(path, profile, task, seed, repetition)
    _binding_paths(binding_path, binding, e.harness)
    scenario = e.scenario(task, seed, repetition)
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    request = {"schema_version": 1, "harness": e.harness, "episode_id": scenario.id,
               "task_id": task, "seed": seed, "repetition": repetition, "layout": scenario.layout,
               "instruction": scenario.instruction, "objects": scenario.objects, "targets": scenario.targets,
               "corrections": scenario.corrections, "mask_instruction_after": scenario.mask_instruction_after,
               "limits": e.limits, "evaluation_backend": profile["evaluation_backend"],
               "source": TASKS[task].source, "output": str(folder),
               "binding_file": str(binding_path), "repo_root": profile["repo_root"]}
    # Scorer truth is deliberately absent from the child request. The trusted
    # native environment/evaluator must export independently measured evidence.
    write_json(folder / "request.json", request)
    inputs = {}
    for key in ("config_file", "program_file"):
        if binding.get(key):
            p = Path(binding[key]).expanduser()
            inputs[key] = digest(p if p.is_absolute() else binding_path.parent / p)
    write_json(folder / "provenance.json", {"harness": e.harness, "upstream_url": UPSTREAMS[e.harness]["url"],
               "revision": profile["revision"], "binding_sha256": digest(binding_path),
               "native_input_sha256": inputs,
               "profile_sha256": digest(path), "scenario_sha256": hashlib.sha256(json.dumps(asdict(scenario), sort_keys=True).encode()).hexdigest(),
               "adapter_sha256": digest(__file__), "worker_sha256": digest(Path(__file__).with_name("upstream_worker.py"))})
    command = [profile["python"], str(Path(__file__).with_name("upstream_worker.py")), "--request", str(folder / "request.json")]
    env = dict(os.environ)
    # Avoid injecting the GaP interpreter's dependencies into Python 3.11 upstreams.
    env.pop("PYTHONPATH", None)
    env.update(JEVGAP_REQUEST=str(folder / "request.json"), JEVGAP_OUTPUT=str(folder), PYTHONIOENCODING="utf-8")
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    started = time.monotonic()
    with (folder / "upstream.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=Path(profile["repo_root"]) / UPSTREAMS[e.harness]["cwd"],
                                   env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        try:
            code = process.wait(timeout=profile.get("timeout_s", 600))
        except BaseException:
            try:
                _terminate(process)
            finally:
                write_json(folder / "process.json", {"completed": False, "elapsed_s": time.monotonic()-started})
            raise
    write_json(folder / "process.json", {"completed": True, "returncode": code, "elapsed_s": time.monotonic()-started})
    return normalize(folder, scenario, e.harness, code, profile["evaluation_backend"])
