import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

if os.environ.get("GAP_ROOT"):
    gap_root = Path(os.environ["GAP_ROOT"])
    sys.path[:0] = [str(gap_root), str(gap_root / "gap-core/src")]

from rtbench_tasks.catalog import TASKS
from rtbench_tasks.config import Experiment, preflight
from rtbench_tasks.experiment import initialize, run, session_outcome
from rtbench_tasks.replay import fixture
from rtbench_tasks.responses import ResponsesPolicy
from rtbench_tasks.se3 import GraphPolicy, JointPlan, SDKTypes, SE3Backend, Verification


def station_spec():
    return SimpleNamespace(arms={"left": SimpleNamespace(n_arm_dof=6, n_gripper_dof=1, control_rate=100.0)}, cameras={})


def observation(stamp):
    return SimpleNamespace(arms={"left": SimpleNamespace(timestamp=stamp, joint_angle_q=np.zeros(6, np.float32),
                                                         gripper_pos=np.ones(1, np.float32))}, cameras={})


class DiagnosticDriver:
    """Known-answer stream fixture; explicitly no physics or real perception."""
    calibration_id = "fixture-v1"

    def __init__(self, backend):
        self.replay = backend
        self.capabilities = backend.capabilities
        self.closed = 0

    def validate_station(self, station): pass
    def validate_start_pose(self, pose): pass
    def validate_plan(self, action, plan, latest): pass
    def reset(self, scenario): self.replay.reset(scenario)
    def observe(self, raw): return self.replay.observe().visible

    def plan(self, action, raw):
        return JointPlan({"left": (np.zeros((2, 6)), np.ones((2, 1)))}, 10.0)

    def verify(self, action, command_id, raw):
        o = self.replay.observe()
        result = self.replay.execute(action, command_id, o)
        return Verification(result.status, result.public_feedback)

    def evidence(self): return self.replay.evidence()
    def close(self): self.closed += 1


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = initialize(Path(self.tmp.name) / "local", os.environ["GAP_ROOT"])

    def test_templates_cover_every_task_and_block_live(self):
        replay = Experiment(self.root / "replay.json")
        self.assertEqual(len(replay.trials), 13)
        self.assertTrue(preflight(replay)["configuration_ready"])
        live = preflight(Experiment(self.root / "se3.local.json"))
        self.assertFalse(live["configuration_ready"])
        self.assertFalse(live["hardware_validated"])
        self.assertTrue(any("start_pose" in b for b in live["blockers"]))
        self.assertEqual(len(list((self.root / "scenarios").glob("*.json"))), 13)

    def test_paths_resolve_relative_to_config_not_working_directory(self):
        e = Experiment(self.root / "se3.local.json")
        self.assertEqual(Path(e.model_config()["budget_ledger"]), self.root / "budget.sqlite")

    def test_every_generated_scenario_loads_but_keeps_unconfigured_layout(self):
        e = Experiment(self.root / "se3.local.json")
        for task in TASKS:
            s = e.scenario(task, 0, 0)
            self.assertEqual(s.task_id, task)
            self.assertTrue(s.layout.startswith("UNCONFIGURED"))

    def test_replay_cannot_call_a_live_model(self):
        d = json.loads((self.root / "replay.json").read_text())
        d["model"] = {"provider": "openai-responses"}
        (self.root / "bad.json").write_text(json.dumps(d))
        self.assertFalse(preflight(Experiment(self.root / "bad.json"))["configuration_ready"])

    def test_duplicate_tasks_seeds_and_nonfinite_limits_rejected(self):
        for change in ({"tasks": ["stack-blocks"] * 2}, {"seeds": [0, 0]}, {"limits": {"max_age_ms": float("nan")}}, {"repetitions": True}):
            d = json.loads((self.root / "replay.json").read_text())
            d.update(change)
            (self.root / "bad.json").write_text(json.dumps(d))
            with self.assertRaises(ValueError): Experiment(self.root / "bad.json")

    def test_all_thirteen_batch_reports_and_no_overwrite(self):
        e = Experiment(self.root / "replay.json")
        out = self.root / "results"
        summary = run(e, out)
        self.assertEqual((summary["planned"], summary["successful"]), (13, 13))
        self.assertFalse(summary["ranking_eligible"])
        self.assertEqual(len(list((out / "trials").glob("*.json"))), 13)
        with self.assertRaises(FileExistsError): run(e, out)

    def test_failed_trials_are_retained(self):
        e = Experiment(self.root / "replay.json")
        e.trials = e.trials[:2]
        with patch("rtbench_tasks.runtime.run_episode", side_effect=RuntimeError("private details")):
            summary = run(e, self.root / "failed")
        self.assertEqual(summary["attempted"], 2)
        self.assertEqual(summary["successful"], 0)
        self.assertNotIn("private details", json.dumps(summary))

    def test_partial_workflow_cannot_count_as_batch_success(self):
        e = Experiment(self.root / "replay.json")
        e.trials = e.trials[:1]
        report = {"workflow_completed": False, "task_success": True, "stop_reason": "execution_failure", "error": "failure", "score": {"points": 100}}
        with patch("rtbench_tasks.runtime.run_episode", return_value=report):
            summary = run(e, self.root / "partial")
        self.assertEqual(summary["successful"], 0)
        self.assertEqual(summary["completed"], 0)

    def test_inline_credentials_and_unknown_model_settings_rejected(self):
        cfg = {"model_id": "fixed", "key_file": "key", "budget_ledger": "ledger", "budget_usd": 1, "reservation_usd": 1}
        with self.assertRaises(ValueError):
            ResponsesPolicy({**cfg, "api_key": "do-not-inline"}, transport=lambda _: None)
        station = self.root / "station.local.json"
        d = json.loads(station.read_text()); d["token"] = "do-not-inline"
        station.write_text(json.dumps(d))
        self.assertFalse(preflight(Experiment(self.root / "se3.local.json"))["configuration_ready"])

    def test_real_sdk_job_and_report_boundary_without_connection(self):
        from se3labs.sdk import eval_client
        from se3labs.interface.wire import pb
        from rtbench_tasks.experiment import _run_se3
        scenario, replay, _ = fixture("stack-blocks")
        driver = DiagnosticDriver(replay)
        driver_config = self.root / "driver.local.json"
        driver_config.write_text('{}')
        e = Experiment(self.root / "se3.local.json")
        station = e.station_config()
        station.update(station_id="offline-test", address="unused:1", calibration_id=driver.calibration_id,
                       driver_factory="unused:factory")
        station["reset_instructions"]["stack-blocks"] = "Use prescribed test layout."
        e.model_config = lambda: {"model_id": "fixed", "key_file": "unused.key", "budget_ledger": "unused.sqlite", "budget_usd": 1, "reservation_usd": 1}
        e.station_config = lambda: station
        def serve(station_id, address, request):
            self.assertEqual(request.episodes, 1)
            self.assertEqual(request.task.name, "stack-blocks")
            self.assertEqual(request.task.scoring.success.key, "task_success")
            request.policy.report = {"workflow_completed": True, "task_success": True, "stop_reason": "finish"}
            return eval_client.SessionReport(state="SUCCEEDED", episodes=1,
                                            results=[pb.EpisodeResult(episode_id="1", scored=True, success=True)])
        with patch("rtbench_tasks.se3.load_driver", return_value=driver), patch.object(eval_client, "serve_policy", side_effect=serve):
            row = _run_se3(e, "stack-blocks", 0, 0, self.root/"unused", self.root/"sdk-record")
        self.assertTrue(row["task_success"])
        self.assertTrue(json.loads((self.root/"sdk-record/se3-session.json").read_text())["results"][0]["scored"])
        self.assertEqual(driver.closed, 1)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = {"model_id": "fixed-model", "key_file": "unused.key", "budget_ledger": str(Path(self.tmp.name) / "ledger.sqlite"),
                       "budget_usd": 2, "reservation_usd": 1, "max_output_tokens": 100}
        self.request = {"instruction": None, "memory": "retain this", "skills": {"finish": "done"}, "observation": {}}
        self.answer = {"action": {"skill": "finish", "object_id": "", "target_id": "", "orientation": ""}, "memory": "retain this"}

    def response(self):
        return {"model": "fixed-model", "status": "completed", "usage": {"input_tokens": 50, "output_tokens": 10},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(self.answer)}]}]}

    def test_exact_schema_no_hidden_conversation_and_usage(self):
        payloads = []
        def send(payload):
            payloads.append(payload)
            return self.response()
        p = ResponsesPolicy(self.config, transport=send)
        self.assertEqual(p.decide(self.request), self.answer)
        p.decide(self.request)
        self.assertEqual(payloads[0], payloads[1])
        self.assertFalse(payloads[0]["store"])
        self.assertIsNone(json.loads(payloads[0]["input"])["instruction"])
        self.assertNotIn("previous_response_id", payloads[0])
        self.assertEqual(p.calls[0]["usage"]["output_tokens"], 10)

    def test_explicit_live_required(self):
        with self.assertRaises(ValueError): ResponsesPolicy(self.config)

    def test_budget_shared_between_fresh_instances_and_failures(self):
        def fail(_): raise RuntimeError("sk-secret should not be logged")
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, "reservation retained") as cm:
                ResponsesPolicy(self.config, transport=fail).decide(self.request)
            self.assertNotIn("sk-secret", str(cm.exception))
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            ResponsesPolicy(self.config, transport=lambda _: self.response()).decide(self.request)

    def test_bad_model_incomplete_refusal_and_malformed_response(self):
        bad = []
        r = self.response(); r["model"] = "other-model"; bad.append(r)
        r = self.response(); r["status"] = "incomplete"; bad.append(r)
        r = self.response(); r["output"][0]["content"] = [{"type": "refusal", "refusal": "no"}]; bad.append(r)
        r = self.response(); r["output"][0]["content"][0]["text"] = '{"action": {}, "memory": 4}'; bad.append(r)
        for i, result in enumerate(bad):
            cfg = {**self.config, "budget_ledger": str(Path(self.tmp.name)/f"bad-{i}.sqlite")}
            with self.assertRaises(RuntimeError):
                ResponsesPolicy(cfg, transport=lambda _, r=result: r).decide(self.request)

    def test_oversized_input_rejected_before_reservation(self):
        p = ResponsesPolicy({**self.config, "max_input_bytes": 1}, transport=lambda _: self.response())
        with self.assertRaises(ValueError): p.decide(self.request)
        self.assertFalse(Path(self.config["budget_ledger"]).exists())

    def test_incompatible_ledger_cannot_ignore_previous_spend(self):
        db = sqlite3.connect(self.config["budget_ledger"])
        db.execute("CREATE TABLE calls (cost REAL)")
        db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, "dedicated"):
            ResponsesPolicy(self.config, transport=lambda _: self.response()).decide(self.request)


class OutcomeTests(unittest.TestCase):
    def test_unscored_failed_or_disagreeing_results_never_pass(self):
        for state, episodes, scored, operator_success, local_success, error, stop in (
                ("SUCCEEDED", 1, True, True, True, None, "finish"),
                ("SUCCEEDED", 1, False, True, True, None, "finish"),
                ("FAILED", 1, True, True, True, None, "finish"),
                ("SUCCEEDED", 2, True, True, True, None, "finish"),
                ("SUCCEEDED", 1, True, False, True, None, "finish"),
                ("SUCCEEDED", 1, True, True, False, None, "finish"),
                ("SUCCEEDED", 1, True, True, True, "worker_still_running", "finish"),
                ("SUCCEEDED", 1, True, True, True, None, "abort")):
            session = SimpleNamespace(state=state, episodes=episodes, errors=[], results=[SimpleNamespace(scored=scored, success=operator_success)])
            policy = SimpleNamespace(error=error, report={"workflow_completed": True, "task_success": local_success, "stop_reason": stop})
            result = session_outcome(session, policy)
            expected = state == "SUCCEEDED" and episodes == 1 and scored and operator_success and local_success and not error and stop == "finish"
            self.assertEqual(result["task_success"], bool(expected))

    def test_late_model_finish_cannot_pass_episode_deadline(self):
        from rtbench_tasks.runtime import Session
        scenario, backend, model = fixture("stack-blocks")
        session = Session(scenario, backend, model, episode_timeout_s=1)
        request = session.observe()["request"]
        with patch("rtbench_tasks.runtime.time.monotonic", side_effect=[session.deadline-0.1, session.deadline+0.1]):
            with self.assertRaises(TimeoutError): session.decide(request)
        self.assertEqual(session.stop_reason, "episode_timeout")


class SE3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdk = SDKTypes()  # Actual pinned SDK interface, never a network client.

    def make_backend(self, **kwargs):
        s, replay, p = fixture("stack-blocks")
        backend = SE3Backend(DiagnosticDriver(replay), station_spec(), sdk=self.sdk, **kwargs)
        backend.reset(s)
        self.addCleanup(backend.close)
        return s, backend, p

    def test_actual_sdk_shapes_units_and_station_time(self):
        plan = JointPlan({"left": (np.zeros((4, 6)), np.ones((4, 1)))}, 10.0)
        chunk = self.sdk.chunk(plan, station_spec(), 123.5)
        self.assertEqual(chunk.timestamp, 123.5)
        self.assertEqual(chunk.horizon, 4)
        self.assertEqual(chunk.arms["left"].joint_angle_q.dtype, np.float32)

    def test_invalid_plans_rejected(self):
        cases = [JointPlan({"right": (np.zeros((4, 6)), np.ones((4, 1)))}, 10),
                 JointPlan({"left": (np.zeros((4, 5)), np.ones((4, 1)))}, 10),
                 JointPlan({"left": (np.zeros((4, 6)), np.ones((4, 1))*2)}, 10),
                 JointPlan({"left": (np.full((4, 6), np.nan), np.ones((4, 1)))}, 10),
                 JointPlan({"left": (np.zeros((4, 6)), np.ones((4, 1)))}, 101)]
        for plan in cases:
            with self.assertRaises((ValueError, TypeError)): self.sdk.chunk(plan, station_spec(), 1.0)

    def test_submission_does_not_mean_completion(self):
        s, b, p = self.make_backend(command_timeout_s=0.5)
        b.publish(observation(1))
        obs = b.observe()
        action = b.driver.replay.actions[0]
        result = []
        t = threading.Thread(target=lambda: result.append(b.execute(action, "cmd", obs)))
        t.start()
        self.addCleanup(lambda: (b.close(), t.join(1)))
        end = time.monotonic()+1
        while b.pending is None and time.monotonic() < end: time.sleep(0.001)
        self.assertIsNotNone(b.next_chunk())
        self.assertEqual(result, [])
        self.assertIsNone(b.next_chunk())
        b.publish(observation(2))
        t.join(1)
        self.assertEqual(result[0].status, "completed")
        self.assertTrue(b.checkpoint()["verified"])

    def test_clock_regression_and_duplicate_packets(self):
        _, b, _ = self.make_backend()
        b.publish(observation(2))
        captured = b.latest_ns
        b.publish(observation(2))
        self.assertEqual(b.latest_ns, captured)
        self.assertEqual(b.sequence, 1)
        with self.assertRaises(ValueError): b.publish(observation(1))

    def test_close_unblocks_wait_and_drops_pending_chunk(self):
        _, b, _ = self.make_backend()
        b.pending = object()
        b.close()
        self.assertIsNone(b.next_chunk())
        with self.assertRaises(RuntimeError): b.observe()

    def test_expired_planning_observation_never_queues(self):
        _, b, _ = self.make_backend(max_age_ms=1)
        b.publish(observation(1))
        obs = b.observe()
        b.latest_ns -= 10_000_000  # Windows monotonic clock may tick only every ~16 ms.
        with self.assertRaises(TimeoutError): b.execute(b.driver.replay.actions[0], "cmd", obs)
        self.assertIsNone(b.pending)

    def test_bad_callback_ends_episode_instead_of_continuing_old_chunk(self):
        scenario, replay, model = fixture("stack-blocks")
        driver = DiagnosticDriver(replay)
        policy = GraphPolicy(scenario, model, driver, {"start_pose": {"left": {"joints": [0]*6, "gripper": [1]}}},
                             Path("unused"), Path("unused"), {"command_timeout_s": 1, "max_age_ms": 2000}, sdk=self.sdk)
        policy.initialize(station_spec(), None)
        policy.backend.publish(observation(2))
        with self.assertRaises(self.sdk.EndEpisode): policy.infer(observation(1))
        self.assertTrue(policy.backend.closed)
        self.assertEqual(policy.error, "ValueError")
        policy.reset()
        with self.assertRaises(RuntimeError): policy.initialize(station_spec(), None)

    def test_pending_verification_times_out_without_permitting_next_command(self):
        _, b, _ = self.make_backend(command_timeout_s=0.04)
        b.driver.verify = lambda *args: Verification("pending")
        b.publish(observation(1))
        obs = b.observe()
        errors = []
        def execute():
            try: b.execute(b.driver.replay.actions[0], "cmd", obs)
            except Exception as exc: errors.append(type(exc))
        worker = threading.Thread(target=execute)
        worker.start()
        self.addCleanup(lambda: (b.close(), worker.join(1)))
        deadline = time.monotonic()+1
        while b.pending is None and time.monotonic() < deadline: time.sleep(0.001)
        self.assertIsNotNone(b.next_chunk())
        b.publish(observation(2))
        worker.join(1)
        self.assertEqual(errors, [TimeoutError])
        with self.assertRaises(RuntimeError): b.execute(b.driver.replay.actions[0], "cmd2", obs)

    def test_all_thirteen_graphs_through_sdk_lifecycle(self):
        from rtbench_tasks.graphs import build_all
        with tempfile.TemporaryDirectory() as temp:
            graphs = build_all(Path(temp)/"graphs")
            for task in TASKS:
                with self.subTest(task=task):
                    scenario, replay, model = fixture(task)
                    driver = DiagnosticDriver(replay)
                    limits = {"max_decisions": 64, "memory_chars": 8000, "max_age_ms": 2000,
                              "episode_timeout_s": 10, "command_timeout_s": 1}
                    policy = GraphPolicy(scenario, model, driver, {"start_pose": {"left": {"joints": [0]*6, "gripper": [1]}}},
                                         graphs/task, Path(temp)/"runs"/task, limits, sdk=self.sdk)
                    policy.initialize(station_spec(), None)
                    chunks = 0
                    end = time.monotonic()+10
                    try:
                        tick = 0
                        while time.monotonic() < end:
                            tick += 1
                            try:
                                chunks += policy.infer(observation(tick/100)) is not None
                            except self.sdk.EndEpisode:
                                break
                            time.sleep(0.002)
                    finally:
                        policy.reset()
                        policy.reset()
                    self.assertIsNone(policy.error)
                    self.assertTrue(policy.report["workflow_completed"], policy.report)
                    self.assertTrue(policy.report["task_success"])
                    self.assertEqual(chunks, len(replay.actions))
                    self.assertEqual(driver.closed, 1)


if __name__ == "__main__": unittest.main()
