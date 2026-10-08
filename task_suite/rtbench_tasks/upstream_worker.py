"""Standalone Python 3.11+ worker running real upstream APIs in their own envs.

No rtbench_tasks/SE3/GaP import is needed in the upstream interpreter.
"""
import argparse
import importlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, data):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)


def resolved(binding_path, value):
    p = Path(value).expanduser()
    return str(p.resolve() if p.is_absolute() else (binding_path.parent / p).resolve())


def enpire(request, binding, binding_path, output):
    from enpire.env.forge.artifacts import ArtifactStore
    from enpire.env.forge.loop import TrialRunner

    def make(field, kwargs):
        module, name = binding[field].split(":", 1)
        return getattr(importlib.import_module(module), name)(**kwargs)

    # A native environment can read JEVGAP_REQUEST for task/seed/output and
    # JEVGAP_OUTPUT to export evidence.json. Private truth is not a policy input.
    environment = make("environment_factory", binding.get("environment_kwargs", {}))
    policy = None
    runner = None
    try:
        policy = make("policy_factory", binding.get("policy_kwargs", {}))
        runner = TrialRunner(environment, policy, max_steps=binding.get("max_steps", 64), artifacts=ArtifactStore(output / "native"))
        result = runner.run(seed=request["seed"])
        write(output / "enpire-trial.json", asdict(result))
        return {"execution_ok": True, "native_success": result.success,
                "native_score": result.verification.score if result.verification.score is not None else float(result.success)}
    finally:
        if runner:
            runner.close()
        else:
            try:
                if policy:
                    policy.close()
            finally:
                environment.close()


def cap(request, binding, binding_path, output):
    import tyro
    from capx.envs import launch, runner
    captured = []
    original = runner._print_and_save_summary

    def record(summaries, args, config, start_time):
        captured.extend(summaries)
        return original(summaries, args, config, start_time)

    runner._print_and_save_summary = record
    argv = ["--config-path", resolved(binding_path, binding["config_file"]),
            *binding.get("args", []), "--total-trials", "1", "--num-workers", "1",
            "--output-dir", (output / "native").as_posix()]
    try:
        args = tyro.cli(launch.LaunchArgs, args=argv)
        # Override YAML too: the native web UI is an interactive, unbounded loop.
        args.web_ui = False
        launch.main(args)
    finally:
        runner._print_and_save_summary = original
    if len(captured) != 1:
        raise ValueError("CaP-X must return exactly one native trial summary")
    result = captured[0]
    write(output / "cap-trial.json", asdict(result))
    # CaP-X success concerns execution; task_completed is its separate task flag.
    return {"execution_ok": result.success, "native_success": result.task_completed is True, "native_score": result.reward}


def aspire(request, binding, binding_path, output):
    root = Path(request["repo_root"]) / "aspire/real"
    command = [sys.executable, str(root / "run_script.py"), *binding.get("args", []),
               f"script_file={resolved(binding_path, binding['program_file'])}",
               f"script_output_dir={output / 'native'}", f"env.seed={request['seed']}",
               f"hydra.run.dir={output / 'hydra'}"]
    code = subprocess.call(command, cwd=root, stdin=subprocess.DEVNULL)
    result = read(output / "native/result.json")
    if type(result.get("success")) is not bool or not isinstance(result.get("feedback"), str):
        raise ValueError("ASPIRE result lacks an explicit success judgement")
    # At the pinned revision run_script catches execution exceptions and exits 0.
    # _save_result records that failure on a separate feedback line beginning error=.
    caught_error = any(line.startswith("error=") for line in result["feedback"].splitlines())
    judgement_error = bool(result.get("details", {}).get("error"))
    return {"execution_ok": code == 0 and not caught_error and not judgement_error,
            "native_success": result["success"], "native_score": result.get("score", 0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    request = read(args.request)
    binding_path = Path(request["binding_file"])
    binding, output = read(binding_path), Path(request["output"])
    root = Path(request["repo_root"])
    sys.path.insert(0, str(root))
    result = {"schema_version": 1, "harness": request["harness"], "episode_id": request["episode_id"],
              "execution_ok": False, "native_success": False, "native_score": 0}
    try:
        result.update({"cap": cap, "aspire": aspire, "enpire": enpire}[request["harness"]](request, binding, binding_path, output))
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        print(f"Upstream worker failed: {type(exc).__name__}", file=sys.stderr)
    write(output / "upstream-result.json", result)
    return 0 if result["execution_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
