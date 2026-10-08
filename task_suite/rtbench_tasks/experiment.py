"""One configuration, all selected tasks, append-only trial artifacts."""
import argparse
import copy
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .catalog import TASKS
from .config import Experiment, GAP_COMMIT, preflight


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)


def initialize(directory, gap_root):
    """Generate local setup files. No credentials, model requests, imports or motion."""
    from .replay import fixture
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    config = {"schema_version": 1, "name": "native-gap-13-tasks", "mode": "replay", "harness": "native-gap", "tasks": "all",
              "seeds": [0], "repetitions": 1, "gap_root": str(Path(gap_root).resolve()),
              "station_config": "station.local.json", "scenario_dir": "scenarios",
              "model": {"provider": "replay"},
              "limits": {"max_decisions": 64, "max_age_ms": 2000, "memory_chars": 8000,
                         "episode_timeout_s": 180, "command_timeout_s": 30}}
    write_json(root / "replay.json", config)
    live = copy.deepcopy(config)
    live.update(mode="se3", name="se3-native-gap-13-tasks")
    live["model"] = {"provider": "openai-responses", "model_id": "REPLACE-exact-model-id",
                     "key_file": "REPLACE-with-private-key-file", "budget_ledger": "budget.sqlite",
                     "budget_usd": 0, "reservation_usd": 0, "max_input_bytes": 64000,
                     "max_output_tokens": 2048, "timeout_s": 60, "reasoning_effort": "low"}
    write_json(root / "se3.local.json", live)
    write_json(root / "station.local.json", {
        "station_id": "", "address": "", "calibration_id": "", "start_pose": {},
        "driver_factory": "", "driver_config": "driver.local.json", "validated_tasks": [],
        "press_protocol": "", "reset_instructions": {task: "" for task in TASKS}})
    (root / ".gitignore").write_text("*\n", encoding="utf-8")
    for task in TASKS:
        scenario, _, _ = fixture(task)
        data = asdict(scenario)
        data["layout"] = "UNCONFIGURED-physical-layout"
        write_json(root / "scenarios" / f"{task}--0--0.json", data)
    from .upstream import write_templates
    write_templates(root, config)
    return root


def run(experiment, output, *, live=False):
    e = experiment
    readiness = preflight(e)
    if not readiness["configuration_ready"]:
        raise ValueError("configuration blocked: " + "; ".join(readiness["blockers"]))
    if e.data["mode"] != "replay" and not live:
        raise ValueError("SE3/model requests and upstream processes require --live")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    # Store hashes rather than credential paths or private station configuration.
    write_json(out / "manifest.json", {"schema_version": 1, "name": e.data["name"],
               "mode": e.data["mode"], "harness": e.harness, "config_sha256": hashlib.sha256(e.path.read_bytes()).hexdigest(),
               "tasks": e.tasks, "trials": e.trials, "limits": e.limits,
               "model_id": e.data.get("model", {}).get("model_id", "upstream-configured" if e.harness != "native-gap" else "diagnostic-recorded-policy"),
               "gap_commit": GAP_COMMIT if e.harness == "native-gap" else None,
               "official_submission": False, "ranking_eligible": False})
    if e.harness == "native-gap":
        from .graphs import build_all
        from .replay import fixture
        from .runtime import run_episode
        graphs = build_all(out / "graphs")
    rows = []
    for index, (task, seed, repetition) in enumerate(e.trials):
        trial_id = f"{index:04d}-{task}-s{seed}-r{repetition}"
        folder = out / "runs" / trial_id
        row = {"trial_id": trial_id, "task_id": task, "seed": seed, "repetition": repetition,
               "status": "error", "task_success": False, "mode": e.data["mode"], "harness": e.harness}
        try:
            if e.harness != "native-gap":
                from .upstream import run_trial
                row.update(run_trial(e, task, seed, repetition, folder, live=live))
            elif e.data["mode"] == "replay":
                scenario, backend, policy = fixture(task, seed)
                limits = {k: v for k, v in e.limits.items() if k != "command_timeout_s"}
                report = run_episode(scenario, backend, policy, graphs / task, folder, **limits)
                row.update(status="completed" if report["workflow_completed"] else "error",
                           task_success=bool(report["workflow_completed"] and report["task_success"] and report["stop_reason"] == "finish"),
                           score=report["score"], error=report["error"])
            else:
                row.update(_run_se3(e, task, seed, repetition, graphs / task, folder))
        except Exception as exc:
            # Keep every failed attempt, but never serialize third-party exception bodies.
            row["error_type"] = type(exc).__name__
        write_json(out / "trials" / f"{trial_id}.json", row)
        rows.append(row)
        if e.data["mode"] != "replay" and row["status"] == "error":
            break  # A disconnected/unresolved station must not start another episode.
    summary = {"schema_version": 1, "mode": e.data["mode"], "harness": e.harness, "planned": len(e.trials), "attempted": len(rows),
               "completed": sum(r["status"] == "completed" for r in rows),
               "successful": sum(r["task_success"] is True for r in rows),
               "unattempted": len(e.trials) - len(rows), "trials": rows,
               "ranking_eligible": False, "official_submission": False,
               "interpretation": {"replay": "Known-answer software diagnostics only",
                                  "se3": "Custom YAM task adaptation; operator and local scores retained separately",
                                  "upstream": "Upstream workflow evaluation; native and independent local scores retained separately; budgets and task ports require validation"}[e.data["mode"]]}
    write_json(out / "summary.json", summary)
    return summary


def _run_se3(experiment, task, seed, repetition, graph, folder):
    from google.protobuf.json_format import MessageToDict
    from se3labs.interface.eval.job import JobRequest
    from se3labs.sdk import eval_client
    from .responses import ResponsesPolicy
    from .se3 import GraphPolicy, load_driver, task_spec
    e = experiment
    scenario, station = e.scenario(task, seed, repetition), e.station_config()
    driver = load_driver(station["driver_factory"], config_path=station["driver_config"], calibration_id=station["calibration_id"])
    policy = None
    try:
        needed = set(TASKS[task].skills) | {"home"}
        if not needed.issubset(driver.capabilities):
            raise ValueError("station driver lacks task skills")
        model = ResponsesPolicy(e.model_config(), live=True)
        policy = GraphPolicy(scenario, model, driver, station, graph, folder, e.limits)
        request = JobRequest(task=task_spec(scenario, station, e.limits["episode_timeout_s"]), policy=policy, episodes=1)
        session = eval_client.serve_policy(station["station_id"], station["address"], request)
    finally:
        # Covers network failure paths as well as the SDK's normal reset.
        if policy is not None:
            policy.reset()
        else:
            driver.close()
    result = {"state": session.state, "close_reason": session.close_reason,
              "error_count": len(session.errors), "episodes": session.episodes,
              "results": [MessageToDict(r, preserving_proto_field_name=True) for r in session.results],
              "bridge_error": policy.error}
    write_json(folder / "se3-session.json", result)
    write_json(folder / "deployment.json", {"calibration_id": station["calibration_id"],
               "driver_factory": station["driver_factory"], "sdk_version": "0.0.1",
               "station_config_sha256": hashlib.sha256(e.resolve(e.data["station_config"]).read_bytes()).hexdigest(),
               "driver_config_sha256": hashlib.sha256(Path(station["driver_config"]).read_bytes()).hexdigest()})
    return session_outcome(session, policy)


def session_outcome(session, policy):
    """Keep transport success, operator scoring and measured local success distinct."""
    integration_ok = (session.state == "SUCCEEDED" and session.episodes == 1 and not session.errors
                      and not policy.error and bool(policy.report and policy.report["workflow_completed"]))
    scored = len(session.results) == 1 and session.results[0].scored
    success = bool(integration_ok and scored and session.results[0].success and policy.report["task_success"]
                   and policy.report["stop_reason"] == "finish")
    return {"status": "completed" if integration_ok and scored else "error", "task_success": success,
            "operator_scored": bool(scored), "operator_success": bool(scored and session.results[0].success),
            "local_score": policy.report.get("score") if policy.report else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Configure GaP, CaP-X, ASPIRE or ENPIRE for the 13-task suite")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create local configurations for all four harnesses")
    init.add_argument("--directory", type=Path, required=True)
    init.add_argument("--gap-root", type=Path, required=True)
    sub.add_parser("harnesses", help="list implemented upstream entry points")
    for name in ("doctor", "plan", "batch"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "batch":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print(initialize(args.directory, args.gap_root))
            return 0
        if args.command == "harnesses":
            from .upstream import UPSTREAMS
            print(json.dumps({"native-gap": {"name": "Native GaP", "revision": GAP_COMMIT,
                                             "modes": ["replay", "se3"]}, **UPSTREAMS}, indent=2))
            return 0
        e = Experiment(args.config)
        if args.command in {"doctor", "plan"}:
            status = preflight(e)
            if args.command == "plan":
                status["trials"] = [{"task_id": t, "seed": s, "repetition": r} for t, s, r in e.trials]
                status["execution_requested"] = False
            print(json.dumps(status, indent=2))
            return 0 if status["configuration_ready"] else 2
        if e.harness == "native-gap" and e.data.get("gap_root"):
            gap = e.resolve(e.data["gap_root"])
            sys.path[:0] = [str(gap), str(gap / "gap-core/src")]
        summary = run(e, args.output, live=args.live)
        print(json.dumps(summary, indent=2))
        return 0 if summary["successful"] == summary["planned"] else 1
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
