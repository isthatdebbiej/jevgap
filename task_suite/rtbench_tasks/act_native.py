"""Native policy runners for SE3 ACT tools; no semantic manipulation driver.

GaP executes model-authored bounded graphs with explicit model memory. CaP
uses its pinned multi-turn code loop with a restricted Python environment.
Execution results are not operator task scores.
"""
import io
import json
import signal
import time
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

from .act_agent import prompt
from .act_code import SAFE_BUILTINS, compile_policy
from .cap_costplusiq import native_transport
from .upstream_worker import cap_deadline


class Routed(TypedDict):
    route: str


class GapTools:
    def __init__(self, robot, client, instruction, max_decisions=64):
        self.robot, self.client, self.instruction = robot, client, instruction
        self.memory, self.calls, self.max_decisions = "", 0, max_decisions

    def step(self) -> Routed:
        if self.calls >= self.max_decisions:
            raise RuntimeError("decision budget exhausted")
        messages = prompt(self.robot, self.instruction, self.memory)
        self.client.config["timeout_s"] = min(60, max(0.1, self.robot.deadline-time.monotonic()))
        result = self.client.query(SimpleNamespace(model=self.client.model_id), messages)
        self.robot.status()  # Reject a late reply before any dispatch.
        self.calls += 1
        text = result["content"].strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        decision = json.loads(text)
        if set(decision) != {"tool", "arguments", "memory"} or not isinstance(decision["memory"], str) or len(decision["memory"]) > 8000:
            raise ValueError("invalid tool decision or memory")
        self.memory = decision["memory"]
        self.robot.journal({"kind":"gap_decision", "decision":decision})
        self.robot.call(decision["tool"], decision["arguments"])
        return {"route":"done" if self.robot.ended else "again"}


def run_supplied_gap(robot, client, instruction, output):
    from gap.builder import Workflow
    from gap.runtime.executor import WorkflowExecutor
    from gap_core.tools import ToolRegistry
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    workflow = Workflow(name="act-tools", description="Supplied ACT tool graph; model chooses each action and memory.")
    workflow.add_node("step", type="tool", tool="act.step")
    workflow.add_node("done", type="end", status="success")
    workflow.add_edge("START", "step")
    workflow.add_conditional_edges("step", {"again":"step", "done":"done"}, router_field="route")
    workflow.save(root / "workflow.json")
    loop, registry = GapTools(robot, client, instruction), ToolRegistry()
    registry.register_callable("act.step", loop.step, summary="observe, decide, execute one ACT tool")
    executor = WorkflowExecutor(root, tool_registry=registry, trace_dir=root / "trace",
                                max_node_workers=1, node_visit_cap=66)
    try:
        executor.execute()
        result = {"policy_variant":"native-gap-supplied-act-graph", "execution_ok":executor.exit_status == "success",
                  "task_success":None, "scoring_source":"SE3 operator", "decision_count":loop.calls}
        (root / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        executor.close()
        robot.stop()


class CapEnv:
    low_level_env = object()

    def __init__(self, robot, instruction):
        self.robot, self.instruction = robot, instruction
        self.started = False
        self.namespace = {"robot":robot, "__builtins__":SAFE_BUILTINS}

    def observation(self):
        return {"full_prompt":prompt(self.robot, self.instruction, code=True)}

    def reset(self, **kwargs):
        if self.started:
            raise RuntimeError("physical episode cannot be retried")
        self.started = True
        return self.observation(), {}

    def step(self, code):
        stdout, stderr = io.StringIO(), io.StringIO()
        rc = 0
        try:
            self.robot.status()
            compiled = compile_policy(code)
            # Validate the entire block before executing any robot call.
            # Persistent variables are policy-owned episode memory.
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(compiled, self.namespace)
        except BaseException as exc:
            rc = 1
            stderr.write(type(exc).__name__)
            self.robot.stop()
        terminal = self.robot.ended
        if terminal:
            stderr.write("\nterminated episode")
        info = {"sandbox_rc":rc, "stdout":stdout.getvalue()[-16000:],
                "stderr":stderr.getvalue()[-16000:], "task_completed":False}
        self.robot.journal({"kind":"cap_code", "code":code,"info":info})
        return ({} if terminal else self.observation()), 0.0, terminal, False, info


MULTITURN = """Continue using the latest robot observation and the documented robot.call API.
Previous code:
{executed_code}
stdout:
{console_stdout}
stderr:
{console_stderr}
Return regenerate with the next Python code block if more work is needed.
End with robot.call('robot_end_episode', {{}}) when done or unable to proceed.
"""


def run_cap(robot, client, instruction, output):
    from capx.envs.launch import LaunchArgs
    from capx.envs.trial import _run_single_trial
    from capx.envs import trial
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    args = LaunchArgs(config_path="act-tools", model=client.model_id)
    config = {"output_dir":str(root), "record_video":False, "use_img_differencing":False,
              "use_visual_feedback":False, "use_oracle_code":False, "use_parallel_ensemble":False,
              "save_multiturn_prompts":True}
    # Images already occur in every environment prompt for both policies.
    # Disabling the additional CaP render branch avoids duplicated images and
    # unmatched auxiliary vision-model calls.
    robot.status()
    remaining = max(1, int(robot.deadline-time.monotonic()))
    original_query = client.query
    def bounded_query(args, messages):
        robot.status()
        if len(client.calls) >= client.config.get('max_decisions',64):
            raise RuntimeError("model decision budget exhausted")
        client.config["timeout_s"] = min(60, max(0.1, robot.deadline-time.monotonic()))
        result = original_query(args, messages)
        robot.status()
        return result
    started = time.monotonic()
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError("CaP rollout deadline")
    signal.signal(signal.SIGALRM, expired)
    try:
        with cap_deadline(remaining), patch.object(client, "query", bounded_query), native_transport(client), patch.object(trial, "MULTITURN_LIMIT", client.config.get('max_decisions',64)-1):
            signal.alarm(remaining)
            result = _run_single_trial(CapEnv(robot, instruction), 0, args, config, MULTITURN)
        (root / "native-result.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        return {"policy_variant":"native-cap-act-tools", "execution_ok":result.success,
                "task_success":None,"scoring_source":"SE3 operator", "elapsed_monotonic_s":time.monotonic()-started}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        robot.stop()


from .act_gap import run_generated_gap as run_gap
