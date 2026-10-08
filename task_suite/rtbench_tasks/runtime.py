"""Native GaP episode harness with bounded model decisions and audit records."""
import copy
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

from .catalog import TASKS, catalog
from .config import positive
from .contracts import Action, Evidence
from .scoring import evaluate


class Observed(TypedDict):
    request: dict


class Decision(TypedDict):
    route: str
    action: dict


class Dispatched(TypedDict):
    command_id: str


class Session:
    def __init__(self, scenario, backend, policy, *, max_decisions=64, max_age_ms=2000, memory_chars=8000,
                 episode_timeout_s=180, allow_hardware=False):
        if backend.mode not in {"replay", "simulation"} and not (backend.mode == "se3" and allow_hardware is True):
            raise ValueError("physical execution requires an SE3 adapter and explicit run authorization")
        if max_decisions < 1 or max_age_ms <= 0 or memory_chars < 0:
            raise ValueError("invalid episode limits")
        positive(episode_timeout_s, "episode_timeout_s")
        needed = set(TASKS[scenario.task_id].skills) | {"home"}
        if not needed.issubset(backend.capabilities):
            raise ValueError(f"backend lacks skills: {sorted(needed - backend.capabilities)}")
        evaluate(scenario, Evidence(scenario.id, {o: {} for o in scenario.objects}, {}, (), "preflight", "preflight"))
        if not policy.model_id:
            raise ValueError("a fixed model id is required")
        self.scenario, self.backend, self.policy = scenario, backend, policy
        self.model_id = policy.model_id
        self.max_decisions, self.max_age_ms, self.memory_chars = max_decisions, max_age_ms, memory_chars
        self.memory, self.calls, self.previous_sequence = "", 0, -1
        self.events, self.feedback, self.last_receipt = [], "", None
        self.blocked, self.last_dispatched_step = False, -1
        self.observation = None
        self.stop_reason = ""
        self.deadline = time.monotonic() + episode_timeout_s
        backend.reset(scenario)

    def _within_budget(self):
        if time.monotonic() >= self.deadline:
            self.stop_reason = "episode_timeout"
            raise TimeoutError("episode time budget exhausted")

    def _fresh(self, obs):
        age = time.monotonic_ns() - obs.captured_ns
        if obs.episode_id != self.scenario.id or age < 0 or age > self.max_age_ms * 1_000_000:
            raise ValueError("wrong-episode, future or stale observation")

    def observe(self) -> Observed:
        self._within_budget()
        obs = self.backend.observe()
        self._fresh(obs)
        if obs.sequence <= self.previous_sequence:
            raise ValueError("observation sequence must increase")
        self.previous_sequence, self.observation = obs.sequence, obs
        s = self.scenario
        masked = s.mask_instruction_after is not None and self.calls >= s.mask_instruction_after
        request = {
            "episode_id": s.id, "step": self.calls,
            "instruction": None if masked else s.instruction,
            "corrections": [text for step, text in s.corrections if step == self.calls],
            "observation": copy.deepcopy(obs.visible),
            "observation_sequence": obs.sequence,
            "skills": catalog(s.task_id), "memory": self.memory,
            "last_feedback": self.feedback,
            "response_contract": {"action": {"skill": "name", "object_id": "id or empty", "target_id": "id or empty", "orientation": "left/upright/preserve or empty"}, "memory": "updated episode memory"},
        }
        # No private truth, scorer state, hidden initial scene, or answer-bearing
        # task metadata is included. Instruction masking applies to every prompt.
        return {"request": request}

    def decide(self, request: dict) -> Decision:
        self._within_budget()
        if self.calls >= self.max_decisions:
            self.stop_reason = "decision_budget"
            return {"route": "abort", "action": asdict(Action("abort"))}
        start = time.monotonic_ns()
        if self.policy.model_id != self.model_id:
            raise ValueError("policy changed its model id")
        response = self.policy.decide(copy.deepcopy(request))
        self.calls += 1
        self._within_budget()
        if self.policy.model_id != self.model_id:
            raise ValueError("policy changed its model id during the call")
        if not isinstance(response, dict) or set(response) != {"action", "memory"}:
            raise ValueError("policy must return exactly action and memory")
        memory = response["memory"]
        if not isinstance(memory, str) or len(memory) > self.memory_chars:
            raise ValueError("policy memory exceeds configured limit")
        if not isinstance(response["action"], dict):
            raise ValueError("action must be an object")
        action = Action(**response["action"])
        action.validate(self.scenario)
        self.memory = memory
        self.events.append({"kind": "decision", "step": self.calls, "request": request,
                            "response": copy.deepcopy(response), "latency_ns": time.monotonic_ns() - start})
        if action.skill in {"abort", "finish"}:
            self.stop_reason = action.skill
        return {"route": action.skill, "action": asdict(action)}

    def dispatch(self, action: dict) -> Dispatched:
        self._within_budget()
        if self.blocked or self.last_dispatched_step == self.calls:
            raise RuntimeError("dispatch blocked: unresolved command or duplicate decision")
        command = Action(**action)
        command.validate(self.scenario)
        self._fresh(self.observation)  # Includes model latency before dispatch.
        if command.skill not in self.backend.capabilities:
            raise ValueError("backend does not support this action")
        command_id = f"{self.scenario.id}:{self.calls}"
        self.last_dispatched_step = self.calls
        self.blocked = True  # An exception may occur after a command was accepted.
        receipt = self.backend.execute(command, command_id, self.observation)
        self.last_receipt = receipt
        self.events.append({"kind": "command", "action": action, "receipt": asdict(receipt)})
        if receipt.command_id != command_id or receipt.status != "completed" or receipt.verified is not True or receipt.observation_sequence <= self.observation.sequence:
            raise RuntimeError("command not verified complete; no automatic retry or further motion")
        self.feedback = receipt.public_feedback
        return {"command_id": command_id}

    def checkpoint(self):
        # Independent adapter verification, not the model's completion claim.
        r = self.last_receipt
        proof = self.backend.checkpoint()
        verified = (proof.get("verified") is True and r is not None
                    and proof.get("command_id") == r.command_id)
        self.blocked = not verified
        return {"verified": verified}


def run_episode(scenario, backend, policy, graph_dir, output_dir, **limits):
    from gap.runtime.executor import WorkflowExecutor
    from gap_core.tools import ToolRegistry

    graph_bytes = (Path(graph_dir) / "workflow.json").read_bytes()
    if json.loads(graph_bytes).get("meta", {}).get("name") != scenario.task_id:
        raise ValueError("graph does not match the scenario task")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite an existing trial.
    session = Session(scenario, backend, policy, **limits)
    registry = ToolRegistry()
    for name in ("observe", "decide", "dispatch"):
        registry.register_callable(f"se3.{name}", getattr(session, name), summary=name)
    tool_catalog = {name: {"summary": tool.summary,
                          "inputs": {key: field.type_str for key, field in tool.schema.inputs.items()},
                          "outputs": {key: field.type_str for key, field in tool.schema.outputs.items()}}
                    for name, tool in registry.runtime_tools().items()}
    (out / "tool_catalog.json").write_text(json.dumps(tool_catalog, indent=2), encoding="utf-8")
    from gap.skills import SkillsRegistry
    skills = SkillsRegistry()
    skills.discover(Path(graph_dir).parent / "registry" / "skills")
    required_skills = {f"se3-{s}" for s in (*TASKS[scenario.task_id].skills, "home")}
    if any(name not in skills for name in required_skills):
        raise RuntimeError("required GaP skill bundles failed to load")
    executor = WorkflowExecutor(graph_dir, tool_registry=registry, trace_dir=out / "trace",
                                skill_registry=skills,
                                checkpoints="raise", world_snapshot_fn=session.checkpoint,
                                max_node_workers=1, node_visit_cap=session.max_decisions + 2)
    error = None
    try:
        executor.execute()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        executor.close()
    score, evidence = None, None
    try:
        evidence = backend.evidence()
        score = evaluate(scenario, evidence)
    except Exception as exc:
        error = error or f"evaluation failed: {type(exc).__name__}: {exc}"
    report = {
        "schema_version": 1, "task_id": scenario.task_id, "episode_id": scenario.id,
        "seed": scenario.seed, "layout": scenario.layout, "model": session.model_id,
        "policy": "native-gap", "backend": backend.mode,
        "official_submission": False, "ranking_eligible": False,
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        "graph_bundle_sha256": _tree_hash(Path(graph_dir)),
        "suite_source_sha256": _tree_hash(Path(__file__).parent),
        "scenario_sha256": hashlib.sha256(json.dumps(asdict(scenario), sort_keys=True).encode()).hexdigest(),
        "limits": {"max_decisions": session.max_decisions, "max_age_ms": session.max_age_ms, "memory_chars": session.memory_chars,
                   "episode_timeout_s": limits.get("episode_timeout_s", 180)},
        "workflow_completed": executor.exit_status == "success" and error is None,
        "stop_reason": session.stop_reason or "execution_failure", "error": error or (executor._first_node_error if executor.exit_status != "success" else None),
        "task_success": bool(score and score.success), "score": asdict(score) if score else None,
        "decision_count": session.calls,
        "checkpoints": [c.to_dict() for c in executor.checkpoint_results],
        "source": TASKS[scenario.task_id].source,
        "telemetry_ref": evidence.telemetry_ref if evidence else None,
        "provider_calls": copy.deepcopy(getattr(policy, "calls", [])),
    }
    # Evaluation records are a separate artifact, never recycled as a prompt.
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "events.json").write_text(json.dumps(session.events, indent=2), encoding="utf-8")
    if evidence:
        (out / "evaluation.json").write_text(json.dumps(asdict(evidence), indent=2), encoding="utf-8")
    return report


def _tree_hash(directory):
    digest = hashlib.sha256()
    for file in sorted(directory.rglob("*")):
        if file.is_file() and file.suffix in {".py", ".json", ".md", ".toml"}:
            digest.update(file.relative_to(directory).as_posix().encode() + b"\0")
            digest.update(file.read_bytes())
    return digest.hexdigest()
