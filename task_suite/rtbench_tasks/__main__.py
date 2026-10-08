import argparse
import importlib
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "experiment":
        from .experiment import main as experiment_main
        raise SystemExit(experiment_main(sys.argv[2:]))
    parser = argparse.ArgumentParser(description="SE3 13-task suite. Replay checks contracts, not physics or model performance.")
    parser.add_argument("command", choices=("list", "build", "replay", "run"))
    parser.add_argument("--gap-root", type=Path, help="path to the pinned vendor/graph-as-policy checkout")
    parser.add_argument("--output", type=Path, default=Path("outputs/task-suite"))
    parser.add_argument("--task", default="all")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scenario", type=Path, help="private scenario JSON; never passed to the policy")
    parser.add_argument("--model", help="exact model id, pinned for this episode")
    parser.add_argument("--policy", help="local module:factory accepting model_id; implements Policy")
    parser.add_argument("--backend", help="local module:factory returning a simulation Backend")
    parser.add_argument("--max-decisions", type=int, default=64)
    parser.add_argument("--max-age-ms", type=int, default=2000)
    args = parser.parse_args()
    if args.gap_root is None:
        candidate = Path(__file__).resolve().parents[2] / "vendor" / "graph-as-policy"
        if candidate.is_dir():
            args.gap_root = candidate
    if args.gap_root:
        sys.path[:0] = [str(args.gap_root), str(args.gap_root / "gap-core/src")]
    from .catalog import TASKS
    if args.command == "list":
        print(json.dumps([t.public() for t in TASKS.values()], indent=2))
        return
    from .graphs import build_all
    graphs = build_all(args.output / "graphs")
    if args.command == "build":
        print(f"Built and structurally validated {len(TASKS)} native GaP graphs in {graphs}")
        return
    from .replay import fixture
    from .runtime import run_episode
    if args.command == "run":
        if not all((args.scenario, args.model, args.policy, args.backend)):
            parser.error("run requires --scenario, --model, --policy and --backend")
        from .contracts import Scenario
        data = json.loads(args.scenario.read_text(encoding="utf-8"))
        for key in ("objects", "targets", "corrections"):
            if key in data:
                data[key] = tuple(data[key])
        scenario = Scenario(**data)
        def load_factory(entry):
            module, name = entry.split(":", 1)
            return getattr(importlib.import_module(module), name)
        policy = load_factory(args.policy)(model_id=args.model)
        if policy.model_id != args.model:
            parser.error("policy factory changed the requested model id")
        backend = load_factory(args.backend)()
        report = run_episode(scenario, backend, policy, graphs/scenario.task_id,
                             args.output/"runs"/scenario.id,
                             max_decisions=args.max_decisions, max_age_ms=args.max_age_ms)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["workflow_completed"] else 1)
    selected = list(TASKS) if args.task == "all" else [args.task]
    failed = False
    for task_id in selected:
        s, backend, policy = fixture(task_id, args.seed)
        report = run_episode(s, backend, policy, graphs / task_id, args.output / "runs" / s.id,
                             max_decisions=args.max_decisions, max_age_ms=args.max_age_ms)
        ok = report["workflow_completed"] and report["task_success"]
        print(f"{task_id}: {'PASS' if ok else 'FAIL'} (diagnostic replay only)")
        failed |= not ok
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
