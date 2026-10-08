"""Offline adapter tests. Stub runners are protocol fixtures, not baselines."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rtbench_tasks.config import Experiment, preflight
from rtbench_tasks.experiment import initialize, main, run
from rtbench_tasks.replay import fixture
from rtbench_tasks.upstream import UPSTREAMS, _binding_paths, normalize, run_trial
from rtbench_tasks import upstream_worker


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def successful_evidence(task="stack-blocks"):
    scenario, backend, policy = fixture(task)
    backend.reset(scenario)
    # Diagnostic backend has known answers. Never used as a physical result.
    from rtbench_tasks.contracts import Action
    for item in policy.actions:
        action = Action(**item) if isinstance(item, dict) else item
        if action.skill not in {"finish", "abort"}:
            backend.execute(action, "fixture", backend.observe())
    return scenario, asdict(backend.evidence())


class HarnessConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = initialize(Path(self.tmp.name) / "config", os.environ.get("GAP_ROOT", "unused"))

    def test_default_compatible_and_all_thirteen_bindings_per_harness(self):
        d = json.loads((self.root / "replay.json").read_text())
        d.pop("harness")
        save(self.root / "old.json", d)
        self.assertEqual(Experiment(self.root / "old.json").harness, "native-gap")
        for harness in UPSTREAMS:
            e = Experiment(self.root / f"{harness}.local.json")
            self.assertEqual(e.harness, harness)
            self.assertEqual(len(e.trials), 13)
            self.assertEqual(len(list((self.root / "upstream" / harness).glob("*.json"))), 13)
            status = preflight(e)
            self.assertFalse(status["configuration_ready"])
            self.assertFalse(status["hardware_validated"])
            self.assertFalse(any("gap_root" in b for b in status["blockers"]))
        with self.assertRaises(FileExistsError): initialize(self.root, "unused")

    def test_unknown_harness_and_silent_fallback_rejected(self):
        d = json.loads((self.root / "replay.json").read_text())
        for changes in ({"harness": "CaP"}, {"harness": "enpire"}, {"mode": "upstream"}):
            save(self.root / "bad.json", {**d, **changes})
            with self.assertRaises(ValueError): Experiment(self.root / "bad.json")

    def test_plan_and_harness_list_do_not_launch_upstreams(self):
        with patch("rtbench_tasks.upstream.subprocess.Popen", side_effect=AssertionError("must not launch")):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = main(["plan", "--config", str(self.root / "enpire.local.json")])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(len(result["trials"]), 13)
            self.assertFalse(result["execution_requested"])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["harnesses"]), 0)
            self.assertEqual(set(json.loads(output.getvalue())), {"native-gap", *UPSTREAMS})

    def test_overrides_unknown_fields_and_unused_args_rejected(self):
        program = self.root / "program.py"
        program.write_text("pass")
        for args in (["script_output_dir=/tmp"], ["++env.seed=99"], ["--api-key", "private"], ["--output_dir=/tmp"]):
            with self.assertRaises(ValueError):
                _binding_paths(self.root / "binding.json", {"program_file": str(program), "args": args}, "aspire")
        with self.assertRaises(ValueError):
            _binding_paths(self.root / "b.json", {"environment_factory": "x:y", "policy_factory": "x:y", "args": ["ignored"]}, "enpire")

    def test_upstream_budget_cannot_masquerade_as_gap_budget(self):
        d = json.loads((self.root / "enpire.local.json").read_text())
        d["model"]["budget_usd"] = 50
        save(self.root / "bad.json", d)
        self.assertTrue(any("configure the model" in b for b in preflight(Experiment(self.root / "bad.json"))["blockers"]))


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scenario, self.evidence = successful_evidence()
        self.raw = {"schema_version": 1, "harness": "enpire", "episode_id": self.scenario.id,
                    "execution_ok": True, "native_success": True, "native_score": 1.0}
        save(self.root / "upstream-result.json", self.raw)

    def test_native_success_alone_never_passes(self):
        result = normalize(self.root, self.scenario, "enpire", 0, "simulation")
        self.assertEqual(result["error_type"], "missing_independent_evidence")
        self.assertFalse(result["task_success"])

    def test_local_and_native_disagreement_kept_separate(self):
        save(self.root / "evidence.json", self.evidence)
        result = normalize(self.root, self.scenario, "enpire", 0, "simulation")
        self.assertTrue(result["task_success"])
        self.assertFalse(result["ranking_eligible"])
        self.evidence["flags"]["robot_home"] = False
        save(self.root / "evidence.json", self.evidence)
        result = normalize(self.root, self.scenario, "enpire", 0, "simulation")
        self.assertTrue(result["upstream_success"])
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["task_success"])

    def test_nonzero_exit_or_execution_failure_cannot_pass(self):
        save(self.root / "evidence.json", self.evidence)
        for code, ok in ((1, True), (0, False)):
            save(self.root / "upstream-result.json", {**self.raw, "execution_ok": ok})
            self.assertEqual(normalize(self.root, self.scenario, "enpire", code, "simulation")["status"], "error")

    def test_wrong_episode_and_nonfinite_score_rejected(self):
        for change in ({"episode_id": "other"}, {"native_score": float("nan")}, {"native_success": 1}):
            save(self.root / "upstream-result.json", {**self.raw, **change})
            with self.assertRaises(ValueError): normalize(self.root, self.scenario, "enpire", 0, "simulation")

    def test_se3_requires_matching_completed_scored_session(self):
        save(self.root / "evidence.json", self.evidence)
        self.assertEqual(normalize(self.root, self.scenario, "enpire", 0, "se3")["error_type"], "missing_se3_session")
        session = {"episode_id": self.scenario.id, "state": "SUCCEEDED", "episodes": 1,
                   "error_count": 0, "bridge_error": None, "results": [{"scored": True, "success": True}]}
        for change in ({"state": "FAILED"}, {"episode_id": "wrong"}, {"results": [{"success": True}]}, {"error_count": 1}):
            save(self.root / "se3-session.json", {**session, **change})
            self.assertFalse(normalize(self.root, self.scenario, "enpire", 0, "se3")["task_success"])
        save(self.root / "se3-session.json", session)
        self.assertTrue(normalize(self.root, self.scenario, "enpire", 0, "se3")["task_success"])


class ProcessTests(unittest.TestCase):
    """Use an explicitly fake ASPIRE script to exercise real subprocess handling."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = initialize(self.root / "config", "unused")
        self.repo = self.root / "fake-upstream"
        script = self.repo / "aspire/real/run_script.py"
        script.parent.mkdir(parents=True)
        script.write_text('''import json, os, sys, time
from pathlib import Path
request = json.loads(Path(os.environ["JEVGAP_REQUEST"]).read_text())
args = dict(a.split("=", 1) for a in sys.argv[1:])
assert int(args["env.seed"]) == request["seed"]
assert "truth" not in request
program = json.loads(Path(args["script_file"]).read_text())
if program.get("sleep"): time.sleep(30)
output = Path(request["output"])
native = Path(args["script_output_dir"])
native.mkdir(parents=True)
feedback = "reward=1.000, success=True" + ("\\nerror=caught exception" if program.get("caught") else "")
(native / "result.json").write_text(json.dumps({"success": True, "score": 1, "feedback": feedback, "details": {}}))
if program.get("evidence"):
    (output / "evidence.json").write_text(json.dumps(program["evidence"]))
''', encoding="utf-8")
        self.scenario, evidence = successful_evidence()
        self.program = self.root / "program.json"
        save(self.program, {"evidence": evidence})
        path = self.config / "aspire.local.json"
        d = json.loads(path.read_text())
        d["tasks"] = ["stack-blocks"]
        save(path, d)
        self.e = Experiment(path)
        save(self.config / "scenarios/stack-blocks--0--0.json", {**asdict(self.scenario), "layout": "measured-layout-v1"})
        self.profile_path = self.config / "upstream/aspire.local.json"
        self.profile = {"schema_version": 1, "repo_root": str(self.repo), "python": sys.executable,
                        "revision": "a" * 40, "evaluation_backend": "simulation", "timeout_s": 10,
                        "task_config_pattern": "aspire/{task}--{seed}--{repetition}.json"}
        save(self.profile_path, self.profile)
        save(self.config / "upstream/aspire/stack-blocks--0--0.json", {
            "configured": True, "task_id": "stack-blocks", "seed": 0, "repetition": 0,
            "program_file": str(self.program), "args": []})

    def test_process_round_trip_and_provenance_no_overwrite(self):
        folder = self.root / "output"
        row = run_trial(self.e, "stack-blocks", 0, 0, folder, live=True)
        self.assertTrue(row["task_success"])
        self.assertEqual(json.loads((folder / "process.json").read_text())["returncode"], 0)
        self.assertIn("program_file", json.loads((folder / "provenance.json").read_text())["native_input_sha256"])
        self.assertNotIn("truth", json.loads((folder / "request.json").read_text()))
        with self.assertRaises(FileExistsError): run_trial(self.e, "stack-blocks", 0, 0, folder, live=True)

    def test_launch_requires_explicit_live(self):
        with self.assertRaisesRegex(ValueError, "--live"):
            run_trial(self.e, "stack-blocks", 0, 0, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_aspire_caught_exception_with_exit_zero_is_failure(self):
        data = json.loads(self.program.read_text()); data["caught"] = True
        save(self.program, data)
        row = run_trial(self.e, "stack-blocks", 0, 0, self.root / "output", live=True)
        self.assertEqual(row["error_type"], "upstream_execution_failed")

    def test_timeout_preserves_attempt_and_stops_process(self):
        save(self.program, {"sleep": True})
        save(self.profile_path, {**self.profile, "timeout_s": 0.3})
        folder = self.root / "timeout"
        with self.assertRaises(subprocess.TimeoutExpired): run_trial(self.e, "stack-blocks", 0, 0, folder, live=True)
        self.assertFalse(json.loads((folder / "process.json").read_text())["completed"])

    def test_batch_stops_after_failed_upstream_without_gap_import(self):
        self.e.trials *= 2
        save(self.program, {})
        with patch("rtbench_tasks.experiment.preflight", return_value={"configuration_ready": True}), patch("rtbench_tasks.graphs.build_all", side_effect=AssertionError("no GaP fallback")):
            summary = run(self.e, self.root / "batch", live=True)
        self.assertEqual((summary["attempted"], summary["unattempted"], summary["successful"]), (1, 1, 0))
        self.assertEqual(summary["harness"], "aspire")

    def test_doctor_reports_recovery_revision_and_dirty_sources(self):
        with patch("rtbench_tasks.upstream.gap_revision", return_value="b" * 40), patch("rtbench_tasks.upstream.subprocess.run", return_value=SimpleNamespace(stdout=" M file.py")):
            blockers = preflight(self.e)["blockers"]
        self.assertTrue(any("revision" in b for b in blockers))
        self.assertTrue(any("uncommitted" in b for b in blockers))
        self.assertTrue(any("workstation recovery" in b for b in blockers))


class NativeInterfaceTests(unittest.TestCase):
    def test_cap_calls_native_launcher_and_does_not_confuse_execution_with_success(self):
        @dataclass
        class Summary:
            success: bool = True
            task_completed: bool = False
            reward: float = 0.25
        printed = []
        runner = SimpleNamespace(_print_and_save_summary=lambda *args: printed.append(args))
        seen = []
        def parse(cls, args):
            seen.extend(args)
            return SimpleNamespace(web_ui=True)
        def launch_main(args):
            self.assertFalse(args.web_ui)
            runner._print_and_save_summary([Summary()], args, {}, 0)
        modules = {"tyro": SimpleNamespace(cli=parse), "capx.envs": SimpleNamespace(
            launch=SimpleNamespace(LaunchArgs=object, main=launch_main), runner=runner)}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, modules):
            root = Path(tmp)
            result = upstream_worker.cap({}, {"config_file": "task.yaml"}, root / "binding.json", root)
        self.assertTrue(result["execution_ok"])
        self.assertFalse(result["native_success"])
        self.assertEqual(seen[seen.index("--total-trials") + 1], "1")
        self.assertEqual(len(printed), 1)

    def test_enpire_closes_environment_when_policy_factory_fails(self):
        closed = []
        def bad_policy(): raise RuntimeError("fixture failure")
        modules = {"enpire.env.forge.artifacts": SimpleNamespace(ArtifactStore=object),
                   "enpire.env.forge.loop": SimpleNamespace(TrialRunner=object),
                   "fixture_factories": SimpleNamespace(environment=lambda: SimpleNamespace(close=lambda: closed.append(True)), policy=bad_policy)}
        with patch.dict(sys.modules, modules):
            with self.assertRaises(RuntimeError):
                upstream_worker.enpire({}, {"environment_factory": "fixture_factories:environment", "policy_factory": "fixture_factories:policy"}, Path("binding.json"), Path("unused"))
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
