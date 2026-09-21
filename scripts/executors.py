"""A/B infrastructure. Diagnostic providers are tests, never scored experiments."""

import argparse
import functools
import importlib
import json
import os
from pathlib import Path
import socket
import signal
import struct
import subprocess
import sys
import tempfile
import time
from settings import validate_credentials

ROOT = Path(__file__).resolve().parents[1]
GAP = ROOT / "vendor/graph-as-policy"
sys.path[:0] = [str(GAP), str(GAP / "gap-core/src")]
MAX_FRAME = 16 * 1024 * 1024
TOOLS = {"bench.prepare", "bench.decision", "bench.proposal", "bench.identity"}
DECISIONS = {"continue", "reperceive", "replan", "abort"}


def recv(stream):
    def exact(n):
        parts = bytearray()
        while len(parts) < n:
            chunk = stream.recv(n - len(parts))
            if not chunk:
                raise EOFError("runtime disconnected")
            parts.extend(chunk)
        return bytes(parts)

    n = struct.unpack("!I", exact(4))[0]
    if n > MAX_FRAME:
        raise ValueError("oversized frame")
    return json.loads(exact(n))


def send(stream, value):
    data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    if len(data) > MAX_FRAME:
        raise ValueError("oversized frame")
    stream.sendall(struct.pack("!I", len(data)) + data)


def ref_heads(value):
    if isinstance(value, dict):
        if "$ref" in value:
            if len(value) != 1 or not isinstance(value["$ref"], str):
                raise ValueError("invalid ref")
            yield value["$ref"].split(".")[0]
        else:
            for item in value.values():
                yield from ref_heads(item)
    elif isinstance(value, list):
        for item in value:
            yield from ref_heads(item)


def compile_workflow(path):
    """Conservative one-scope subset; rejects more than it attempts to emulate."""
    g = json.loads(Path(path).read_text())
    if set(g) - {"version", "meta", "nodes", "edges", "conditional_edges", "subgraphs"}:
        raise ValueError("UnsupportedGaPFeature: unrecognized workflow fields")
    if g.get("version") != 3 or g.get("conditional_edges") or g.get("subgraphs"):
        raise ValueError("UnsupportedGaPFeature: only unconditional, single-scope fixtures currently implemented")
    nodes = g["nodes"]
    if not nodes or len(nodes) > 64 or "in" in nodes or "START" in nodes or "END" in nodes:
        raise ValueError("invalid nodes")
    incoming = {name: [] for name in nodes}
    outgoing = {name: [] for name in ["START", *nodes]}
    for source, target in g["edges"]:
        if source not in outgoing or target not in nodes:
            raise ValueError("invalid edge")
        if source in incoming[target]:
            raise ValueError("duplicate edge")
        incoming[target].append(source)
        outgoing[source].append(target)
    depth = {"START": -1}
    remaining = set(nodes)
    while remaining:
        ready = [n for n in remaining if incoming[n] and all(p in depth for p in incoming[n])]
        if not ready:
            raise ValueError("cycle or unreachable node")
        for n in ready:
            levels = {depth[p] for p in incoming[n]}
            if len(levels) != 1:
                raise ValueError("ambiguous cross-frontier activation")
            depth[n] = next(iter(levels)) + 1
            remaining.remove(n)
    ends = [n for n, v in nodes.items() if v["type"] == "end"]
    if len(ends) != 1 or nodes[ends[0]].get("status") != "success":
        raise ValueError("one success end required")
    if any(not outgoing[n] and n != ends[0] for n in nodes):
        raise ValueError("unjoined branch")
    if outgoing[ends[0]]:
        raise ValueError("end must be a sink")
    ir = []
    for name, node in nodes.items():
        if set(node) - {"type", "tool", "inputs", "status"}:
            raise ValueError(f"UnsupportedGaPFeature at {name}")
        typ = node["type"]
        if typ not in {"tool", "noop", "end"}:
            raise ValueError(f"UnsupportedGaPFeature: {typ}")
        executable = node.get("tool", typ)
        if typ == "tool" and executable not in TOOLS:
            raise ValueError("unapproved worker; robot tools forbidden")
        heads = set(ref_heads(node.get("inputs", {})))
        parents = set(incoming[name]) - {"START"}
        # Enforce explicit data joins rather than infer arbitrary GaP DAG semantics.
        if len(parents) > 1 and typ == "tool" and not parents.issubset(heads):
            raise ValueError("fan-in needs explicit bindings from every parent")
        ancestors = set()
        todo = list(parents)
        while todo:
            p = todo.pop()
            if p not in ancestors:
                ancestors.add(p)
                todo.extend(x for x in incoming[p] if x != "START")
        if not heads.issubset(ancestors | {"in"}):
            raise ValueError("input is not from a causal ancestor")
        ir.append(
            {
                "id": name,
                "control_preconditions": sorted(parents),
                "input_bindings": node.get("inputs", {}),
                "executable": executable,
            }
        )
    return ir


class Workers:
    def __init__(self, config):
        self.config = config
        self.calls = 0
        self.provider = None
        if config["mode"] == "live":
            entry = config["entrypoint"]
            module, function = entry.split(":", 1)
            self.provider = getattr(importlib.import_module(module), function)
        elif config["mode"] != "diagnostic":
            raise ValueError("unknown worker mode")

    def prepare(self, state: dict) -> dict:
        return {"state": state}

    def decision(self, state: dict) -> dict:
        self.calls += 1
        if self.calls > self.config.get("max_calls", 100):
            raise RuntimeError("configured call budget exhausted")
        begin = time.monotonic_ns()
        if self.provider:
            decision = self.provider(state)
        else:
            time.sleep(self.config.get("diagnostic_delay_s", 0))
            decision = {
                "decision": "replan" if state["scene_version"] != state["committed_scene_version"] else "continue"
            }
        if not isinstance(decision, dict) or set(decision) != {"decision"} or decision["decision"] not in DECISIONS:
            raise ValueError("provider must return exactly one valid decision enum")
        return {
            "decision": {
                "state": state,
                "choice": decision["decision"],
                "request_start_ns": begin,
                "decision_ready_ns": time.monotonic_ns(),
            }
        }

    def proposal(self, decision: dict) -> dict:
        s = decision["state"]
        return {
            "proposal": {
                "source_observation_id": s["observation_id"],
                "source_scene_version": s["scene_version"],
                "source_captured_ns": s["captured_ns"],
                "decision": decision["choice"],
                "target": s["target"],
                "request_start_ns": decision["request_start_ns"],
                "decision_ready_ns": decision["decision_ready_ns"],
            }
        }

    def identity(self, value: dict, other: dict | None = None, delay_s: float = 0) -> dict:
        time.sleep(delay_s)
        return {"value": value, "other": other}

    def invoke(self, name, inputs):
        if name not in TOOLS:
            raise ValueError("worker not allowed")
        return getattr(self, name.split(".")[1])(**inputs)


class Native:
    def __init__(self, workflow, config, trace_dir):
        from gap.runtime.executor import WorkflowExecutor
        from gap_core.tools import ToolRegistry

        compile_workflow(workflow)
        self.workers = Workers(config)
        self.outputs = {}
        self.events = []
        registry = ToolRegistry()
        for name in TOOLS:
            fn = getattr(self.workers, name.split(".")[1])
            registry.register_callable(name, self.wrap(name, fn), summary=name)
        self.executor = WorkflowExecutor(workflow, tool_registry=registry, trace_dir=trace_dir, max_node_workers=8)

    def wrap(self, name, fn):
        @functools.wraps(fn)
        def call(*args, **kwargs):
            begin = time.monotonic_ns()
            result = fn(*args, **kwargs)
            end = time.monotonic_ns()
            self.outputs[name] = result
            self.events.append(
                {"tool": name, "inputs": kwargs, "output": result, "worker_start_ns": begin, "worker_end_ns": end}
            )
            return result

        return call

    def run(self, state, execution_id):
        self.events = []
        self.outputs = {}
        self.executor.initial_inputs = {"state": state}
        start = time.monotonic_ns()
        self.executor.execute()
        return {
            "ok": True,
            "outputs": self.outputs,
            "events": self.events,
            "start_ns": start,
            "end_ns": time.monotonic_ns(),
        }

    def close(self):
        self.executor.close()


class Rust:
    def __init__(self, workflow, config, directory):
        self.nodes = compile_workflow(workflow)
        self.max_calls = config.get("max_calls", 100)
        self.calls = 0
        self.temp = tempfile.TemporaryDirectory(prefix="rtb-")
        folder = Path(self.temp.name)
        cfg = folder / "worker.json"
        cfg.write_text(json.dumps(config))
        self.log = (Path(directory) / "runtime.log").open("w")
        binary = Path(
            os.environ.get("RTBENCH_BINARY", str(Path.home() / ".cache/rtbench/target/release/rtbench-runtime"))
        )
        self.proc = subprocess.Popen(
            [str(binary), str(folder / "rt.sock"), sys.executable, str(Path(__file__).resolve()), str(cfg), "8"],
            stderr=self.log,
            stdout=self.log,
            start_new_session=True,
        )
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(70)
        try:
            limit = time.monotonic() + 30
            begin = time.monotonic_ns()
            while True:
                try:
                    self.socket.connect(str(folder / "rt.sock"))
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    if self.proc.poll() is not None or time.monotonic() > limit:
                        raise RuntimeError("Rust runtime failed to start; inspect runtime.log")
                    time.sleep(0.05)
            handshake = recv(self.socket)
            end = time.monotonic_ns()
            if handshake.get("ready") is not True or not begin <= handshake["clock_ns"] <= end:
                raise RuntimeError("clock domain or startup handshake invalid")
        except BaseException:
            self.close()
            raise

    def run(self, state, execution_id):
        if self.calls >= self.max_calls:
            raise RuntimeError("configured call budget exhausted")
        self.calls += 1
        send(self.socket, {"nodes": self.nodes, "state": state, "execution_id": execution_id})
        result = recv(self.socket)
        if result.get("ok") is not True:
            raise RuntimeError("Rust workflow failed")
        return result

    def close(self):
        try:
            send(self.socket, {"command": "stop"})
        except (OSError, AttributeError):
            pass
        self.socket.close()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
        self.log.close()
        self.temp.cleanup()


def worker(socket_path, config):
    workers = Workers(json.loads(Path(config).read_text()))
    stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stream.connect(socket_path)
    send(stream, {"ready": True})
    while True:
        try:
            request = recv(stream)
        except EOFError:
            return
        start = time.monotonic_ns()
        try:
            result = workers.invoke(request["tool"], request["inputs"])
            send(stream, {"ok": True, "output": result, "start_ns": start, "end_ns": time.monotonic_ns()})
        except Exception as exc:
            # No exception text: provider exceptions may contain authentication details.
            send(stream, {"ok": False, "error_type": type(exc).__name__})


def preflight(config=None):
    validate_credentials()


def diagnostic(output):
    output.mkdir(parents=True, exist_ok=False)
    workflow = ROOT / "workflows/yam_pickup/workflow.json"
    cfg = {"mode": "diagnostic", "diagnostic_delay_s": 0.01, "max_calls": 100}
    native = Native(workflow, cfg, output / "native_trace")
    rust = Rust(workflow, cfg, output)
    state = {
        "observation_id": 1,
        "scene_version": 1,
        "committed_scene_version": 0,
        "captured_ns": time.monotonic_ns(),
        "target": [0, 1, 1.7, -0.4, 0, 0],
    }
    try:
        a = native.run(state, 1)
        b = rust.run(state, 1)

        # Timing differs by design; compare input, invocation count and semantic outputs.
        def canonical(v):
            if isinstance(v, dict):
                return {k: canonical(x) for k, x in v.items() if not k.endswith("_ns")}
            if isinstance(v, list):
                return [canonical(x) for x in v]
            return v

        a_events = [(e["tool"], canonical(e["inputs"]), canonical(e["output"])) for e in a["events"]]
        b_events = [
            (
                next(n["executable"] for n in rust.nodes if n["id"] == e["node"]),
                canonical(e["inputs"]),
                canonical(e["output"]),
            )
            for e in b["events"]
        ]
        assert sorted(a_events) == sorted(b_events)
        result = {
            "status": "passed",
            "kind": "diagnostic conformance only",
            "scored_A_B": False,
            "live_model_calls": 0,
            "worker_invocations_per_path": len(a_events),
            "same_semantic_outputs": True,
        }
        (output / "diagnostic.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    finally:
        native.close()
        rust.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker")
    p.add_argument("--config", type=Path)
    p.add_argument("--diagnostic", type=Path)
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    if args.worker:
        worker(args.worker, args.config)
    elif args.diagnostic:
        diagnostic(args.diagnostic)
    elif args.preflight:
        try:
            preflight()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2)
        print("Credential files found. No API requests made.")
    else:
        p.error("choose --preflight, --diagnostic or --worker")
