"""Qwen-authored ACT graphs executed by the pinned native GaP runtime."""
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

from .act_agent import DEFINITIONS, prompt


GRAPH_CONTRACT = """Return only JSON with exactly memory, start, nodes.
memory: your updated episode memory string, at most 8000 characters.
start: ID of the first node.
nodes: 1 to 8 objects, each with exactly id, tool, arguments, on_success, on_failure.
Use only the supplied ACT tool names and argument fields. Each edge names another
node, 'observe' (end this graph and receive fresh camera images), or 'abort'.
IDs use letters, digits and underscores, starting with a letter. No cycles or
unreachable nodes. Prefer short plans and observe again after manipulation.
Use robot_end_episode to request final scoring. 'observe' does not end the episode.
For robot_end_episode use on_success='observe' and on_failure='abort': the
successful tool call itself ends the episode, so no further observation occurs.
The 'abort' terminal means execution failure, not ordinary successful completion.
An ok tool result means controller completion, not a successful physical effect.
After a no-motion rejection, return to observe and replan from the new scene.
"""


def validate_graph(data):
    if not isinstance(data, dict) or set(data) != {"memory", "start", "nodes"}:
        raise ValueError("invalid graph response fields")
    if not isinstance(data["memory"], str) or len(data["memory"]) > 8000:
        raise ValueError("graph memory limit")
    nodes = data["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 8:
        raise ValueError("graph requires 1 through 8 nodes")
    names = {}
    schemas = {d["name"]:d["parameters"] for d in DEFINITIONS}
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"id","tool","arguments","on_success","on_failure"}:
            raise ValueError("invalid graph node fields")
        name = node["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or name in {"START","END","observe","abort"} or name in names:
            raise ValueError("invalid or duplicate graph node id")
        if not isinstance(node["tool"], str) or node["tool"] not in schemas:
            raise ValueError("unsupported graph tool")
        args, schema = node["arguments"], schemas[node["tool"]]
        if not isinstance(args, dict) or set(args)-set(schema["properties"]) or set(schema["required"])-set(args):
            raise ValueError("invalid graph tool arguments")
        names[name] = node
    if not isinstance(data["start"], str) or data["start"] not in names:
        raise ValueError("invalid graph entry")
    for node in nodes:
        for field in ("on_success", "on_failure"):
            if not isinstance(node[field], str) or node[field] not in {*names, "observe", "abort"}:
                raise ValueError("dangling graph edge")
    visited, active = set(), set()
    def visit(name):
        if name in {"observe", "abort"}: return
        if name in active: raise ValueError("cycles are prohibited in one action graph")
        if name in visited: return
        active.add(name)
        for field in ("on_success", "on_failure"): visit(names[name][field])
        active.remove(name)
        visited.add(name)
    visit(data["start"])
    if visited != set(names):
        raise ValueError("unreachable graph nodes")
    return data


class Outcome(TypedDict):
    route: str


class Tools:
    def __init__(self, robot): self.robot = robot
    def call(self, tool_name: str, arguments: dict) -> Outcome:
        reply = self.robot.call(tool_name, arguments)
        return {"route":"refresh" if reply.get("refresh_observation") else "ok" if reply.get("ok") else "failed"}


def run_generated_gap(robot, client, instruction, output):
    from gap.builder import Workflow
    from gap.runtime.executor import WorkflowExecutor
    from gap_core.tools import ToolRegistry
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    memory, calls, completed = "", 0, False
    started = time.monotonic()
    try:
        while not robot.ended and calls < client.config.get('max_decisions',64):
            messages = prompt(robot, instruction, memory, graph=True)
            messages[0]["content"][0]["text"] += "\n"+GRAPH_CONTRACT
            client.config["timeout_s"] = min(60, max(0.1, robot.deadline-time.monotonic()))
            response = client.query(SimpleNamespace(model=client.model_id), messages)
            robot.status()
            calls += 1
            text = response["content"].strip()
            if text.startswith("```json") and text.endswith("```"): text=text[7:-3].strip()
            data = validate_graph(json.loads(text))
            memory = data["memory"]
            folder = root / f"graph-{calls:03d}"
            folder.mkdir()
            (folder / "model-graph.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            robot.journal({"kind":"generated_graph", "graph":data})
            graph = Workflow(name=f"act-generated-{calls}", description="Model-authored ACT graph, validated before native execution.")
            graph.add_node("observe", type="end", status="success")
            graph.add_node("abort", type="end", status="failure")
            graph.add_edge("START",data["start"])
            for node in data["nodes"]:
                graph.add_node(node["id"], type="tool", tool="act.call", inputs={"tool_name":node["tool"],"arguments":node["arguments"]})
                graph.add_conditional_edges(node["id"], {"ok":node["on_success"],"failed":node["on_failure"],"refresh":"observe"}, router_field="route")
            graph.save(folder / "workflow.json")
            registry=ToolRegistry()
            registry.register_callable("act.call", Tools(robot).call, summary="one bounded ACT tool")
            # The native option caps scheduler steps, not visits per node.
            # A validated DAG needs its action nodes plus its terminal step.
            executor=WorkflowExecutor(folder,tool_registry=registry,trace_dir=folder/"trace",max_node_workers=1,node_visit_cap=len(data["nodes"])+2)
            try:
                executor.execute()
                if executor.exit_status != "success":
                    raise RuntimeError("native graph aborted or a tool failed")
            finally:
                executor.close()
        completed = robot.ended
        result={"policy_variant":"native-gap-model-authored-act-graphs", "execution_ok":completed,
                "task_success":None, "scoring_source":"SE3 operator", "decision_count":calls,
                "elapsed_monotonic_s":time.monotonic()-started}
        (root/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result
    finally:
        robot.stop()
