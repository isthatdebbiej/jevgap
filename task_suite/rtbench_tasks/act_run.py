"""Single-episode ACT service and native policy CLI.

Run service and agent in separate Linux/WSL processes. No service reconnect
loop, auto-retry, or automatic next task. Task files freeze physical wording.
"""
import argparse
import json
import hashlib
import os
import sys
import time
import uuid
from pathlib import Path

from .config import read_json


def load_task(path):
    data = read_json(path)
    required = {"name", "instruction", "reset_instruction", "success_question"}
    if not required.issubset(data) or set(data)-required-{'rubric'} or any(not isinstance(data[k], str) or not data[k].strip() for k in required):
        raise ValueError("task requires name, instruction, reset_instruction and success_question")
    if data["name"] == "press-by-number" and "configured blue-confirm protocol" in data["instruction"]:
        raise ValueError("freeze the exact button/confirmation protocol in the task instruction")
    if data["name"] == "classify-objects-by-language" and "specified by the episode instruction" in data["instruction"]:
        raise ValueError("supply the actual category-to-basket assignment for this episode")
    # Do not silently turn hidden-cue memory tasks into visible-instruction trials.
    if data["name"].startswith("precision-memory") and data["name"] not in {"precision-memory-delayed", "precision-memory-correction", "precision-memory-different-history", "precision-memory-moving-cube"}:
        raise ValueError("this precision/memory variant is not implemented")
    if 'rubric' in data:
        from .act_scoring import validate
        validate(data['rubric'])
    return data


def task_spec(data):
    if data["name"].startswith("precision-memory"):
        from .precision_memory import task_spec as precision_spec
        from dataclasses import replace
        spec=precision_spec(correction=data["name"].endswith(("correction","moving-cube")))
        if data["name"] == "precision-memory-moving-cube":
            def fixture_wording(item):
                return replace(item, prompt=item.prompt.replace("no manual assistance", "no assistance except the prescribed fixture relocation").replace("without manual assistance", "without assistance except the prescribed fixture relocation"))
            # Preserve scoring structure while excluding the experimental
            # intervention itself from the definition of manual assistance.
            spec = replace(spec, scoring=replace(spec.scoring,
                success=fixture_wording(spec.scoring.success),
                items=tuple(fixture_wording(item) for item in spec.scoring.items)))
        return replace(spec,name=data["name"],reset_instruction=spec.reset_instruction+" "+data["reset_instruction"])
    from se3labs.interface.eval.task import Task_Spec, Task_ScoreSheet, Task_ScoreItem, Task_ScoreKind
    from .act_scoring import sheet
    return Task_Spec(name=data["name"], description=data["instruction"],
        instruction=data["instruction"], reset_instruction=data["reset_instruction"], max_rollout_time=450,
        scoring=sheet(data) if 'rubric' in data else Task_ScoreSheet(success=Task_ScoreItem("task_success", data["success_question"], Task_ScoreKind.Binary)))


def serve(args):
    if not args.live or os.name != "posix":
        raise ValueError("ACT service requires Linux/WSL and --live")
    data = load_task(args.task)
    packet=getattr(args,'packet',None)
    commissioning_trial=getattr(args,'commissioning_trial',False)
    if 'rubric' in data or data['name'].startswith('precision-memory'):
        if packet is None:
            raise ValueError('use the frozen operator --packet for study tasks')
        from .act_prepare import verify_packet, digest as packet_digest
        verify_packet(packet,require_commissioned=not commissioning_trial)
        plan=read_json(Path(packet)/'plan.json')
        if packet_digest(data) not in {entry['task_sha256'] for entry in plan}:
            raise ValueError('task does not belong to the frozen operator packet')
    if Path(args.socket).exists():
        raise ValueError("socket already exists; do not attach to an unknown episode")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    from se3labs.sdk.examples.act_harness.policy import ActHarnessPolicy
    from se3labs.interface.eval.job import JobRequest
    from se3labs.sdk import eval_client
    if args.auth_file:
        from se3labs.sdk.auth.config import Environment, ENVIRONMENTS
        auth_path = args.auth_file.resolve()
        if not auth_path.is_file():
            raise ValueError("saved SE3 login file is missing")
        original = ENVIRONMENTS["production"]
        class SavedLogin(Environment):
            @property
            def credentials(self):
                return auth_path
        ENVIRONMENTS["production"] = SavedLogin(original.name, original.api, original.region, original.client_id)
    from google.protobuf.json_format import MessageToDict

    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    class Policy(ActHarnessPolicy):
        def infer(self, observation):
            self.observation_received_ns = time.monotonic_ns()
            return super().infer(observation)
        def reply(self, ok, message):
            result = super().reply(ok, message)
            result.update(episode_id=self.episode_id, task_sha256=digest,
                          max_model_decisions=52 if packet else 64,
                          observation_received_ns=getattr(self, "observation_received_ns", None))
            if self.last_observation is not None:
                for name, arm in self.last_observation.arms.items():
                    if name in result["arms"]:
                        result["arms"][name]["measured_timestamp_s"] = float(arm.timestamp)
            return result

        episode_id = str(uuid.uuid4())
        calibration_id = "sdk-act-kinematics-operator-scored"
        def initialize(self, station, task):
            self.episode_id = str(uuid.uuid4())
            return super().initialize(station, task)

    policy = Policy(keyboard=False, socket_path=args.socket,
                    snapshot_dir=str(out / "live-frames"), snapshot_period_s=0.2)
    # Bundled YAM START_Q is explicit in manifest and operator reset wording.
    manifest = {"task":data, "controller":"se3labs.sdk.examples.act_harness.ActHarnessPolicy",
                "start_q":list(policy.start_q), "station":args.station, "address":args.address,
                "timeout_s":450, "episodes":1, "operator_scored":True,
                "commissioning_trial":commissioning_trial,
                "packet":str(packet) if packet else None}
    if packet:
        manifest['protocol']=read_json(Path(packet)/'protocol.json')
        manifest['commissioning']=read_json(Path(packet)/'commissioning.json')
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = {"state":"FAILED", "task_success":None}
    try:
        session = eval_client.serve_policy(args.station, args.address,
                    JobRequest(task=task_spec(data), policy=policy, episodes=1))
        result = {"state":session.state,"close_reason":session.close_reason,
                  "episodes":session.episodes,"error_count":len(session.errors),
                  "results":[MessageToDict(r,preserving_proto_field_name=True) for r in session.results]}
        if 'rubric' in data:
            from .act_scoring import from_episode
            scores=[]
            for episode in result['results']:
                try:
                    scores.append(dict(from_episode(data,episode),episode_id=episode.get('episode_id')))
                except (ValueError,KeyError,TypeError) as exc:
                    scores.append({'episode_id':episode.get('episode_id'),'valid':False,'error':str(exc)})
            (out/'study-scores.json').write_text(json.dumps(scores,indent=2),encoding='utf-8')
    except BaseException as exc:
        result["error_type"] = type(exc).__name__
        raise
    finally:
        policy.close()
        (out / "se3-session.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def agent(args):
    if not args.live or os.name != "posix":
        raise ValueError("native ACT agent requires Linux/WSL and --live")
    data = load_task(args.task)
    os.environ["CAPX_EXTERNAL_ENV_ONLY"] = "1"
    if args.gap_root:
        sys.path[:0] = [str(args.gap_root), str(args.gap_root / "gap-core/src")]
    if args.cap_root:
        sys.path.insert(0, str(args.cap_root))
    from .act_provenance import verify
    native_root = args.gap_root if args.harness == "native-gap" else args.cap_root
    if not native_root:
        raise ValueError("configure the pinned native checkout path")
    provenance = verify(native_root, args.harness)
    # Import native runners before a rollout starts consuming its 450 seconds.
    if args.harness == "native-gap":
        from gap.runtime.executor import WorkflowExecutor
    else:
        from capx.envs.trial import _run_single_trial
    from .act_agent import Robot
    from .act_native import run_gap, run_cap
    from .cap_costplusiq import NativeClient
    from se3labs.sdk.examples.act_harness.tools import Harness
    cfg = read_json(args.model)
    for name in ("key_file", "budget_ledger"):
        p = Path(cfg[name])
        cfg[name] = str(p if p.is_absolute() else args.model.resolve().parent / p)
    client = NativeClient(cfg, live=True)
    harness = Harness(args.socket, timeout_s=5)
    ready = harness.wait_for_rollout(timeout_s=60)
    if not ready.get("ok") or ready.get("phase") != "rollout":
        raise RuntimeError("no live ACT rollout within 60 seconds; no robot action sent")
    expected = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    if ready.get("task_sha256") != expected:
        raise ValueError("service and policy task manifests differ")
    if ready.get('max_model_decisions') != cfg.get('max_decisions',64):
        raise ValueError('policy decision budget differs from service protocol')
    instruction = data["instruction"]
    if data["name"].startswith("precision-memory"):
        if not args.cues:
            raise ValueError("precision/memory requires --cues for independent observer confirmations")
        from .act_cues import CueFeed
        instruction = CueFeed(args.cues, ready["episode_id"], variant=data["name"].removeprefix("precision-memory-"))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    robot = Robot(harness, out / "robot")
    robot.motion_guard = getattr(instruction, "motion_guard", None)
    try:
        result = (run_gap if args.harness == "native-gap" else run_cap)(robot, client, instruction, out / "native")
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        try:
            robot.stop()
        finally:
            (out / "model-calls.json").write_text(json.dumps(client.calls, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "agent"):
        p = sub.add_parser(name)
        p.add_argument("--task", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--socket", required=True)
        p.add_argument("--live", action="store_true")
        if name == "serve":
            p.add_argument("--auth-file", type=Path)
            p.add_argument("--packet", type=Path)
            p.add_argument("--commissioning-trial",action='store_true',help='Label a supervised commissioning trial; exclude from scored comparisons.')
            p.add_argument("--station", default="se3-labs-yam-2")
            p.add_argument("--address", default="100.107.161.92:7443")
        else:
            p.add_argument("--model", type=Path, required=True)
            p.add_argument("--harness", choices=("native-gap", "cap"), required=True)
            p.add_argument("--gap-root", type=Path)
            p.add_argument("--cap-root", type=Path)
            p.add_argument("--cues", type=Path)
    args = parser.parse_args(argv)
    (serve if args.command == "serve" else agent)(args)


if __name__ == "__main__":
    main()
