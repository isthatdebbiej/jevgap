import copy
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import asdict, replace
from pathlib import Path

if os.environ.get("GAP_ROOT"):
    root = Path(os.environ["GAP_ROOT"])
    sys.path[:0] = [str(root), str(root / "gap-core/src")]

from rtbench_tasks.catalog import TASKS
from rtbench_tasks.contracts import Action, Evidence, Receipt
from rtbench_tasks.replay import fixture, ReplayPolicy
from rtbench_tasks.runtime import Session, run_episode
from rtbench_tasks.scoring import evaluate


class RubricTests(unittest.TestCase):
    def test_all_tasks_positive_and_missing_evidence(self):
        self.assertEqual(len(TASKS), 13)
        for task in TASKS:
            with self.subTest(task=task):
                s, b, _ = fixture(task)
                self.assertEqual(evaluate(s, b.final_evidence).points, 100)
                empty = Evidence(s.id, {o: {} for o in s.objects}, {}, (), "test", "test")
                self.assertEqual(evaluate(s, empty).points, 0)
                with self.assertRaises(ValueError):
                    evaluate(s, replace(empty, episode_id="another-trial"))

    def test_all_tasks_require_home(self):
        for task in TASKS:
            with self.subTest(task=task):
                s, b, _ = fixture(task)
                e = b.final_evidence
                result = evaluate(s, replace(e, flags={**e.flags, "robot_home": False}))
                self.assertLess(result.points, 100)
                self.assertFalse(result.success)

    def test_stack_rejects_cycle_and_separate_stacks(self):
        for task in ("stack-bowls", "stack-blocks"):
            s, b, _ = fixture(task)
            e = copy.deepcopy(b.final_evidence)
            for i, o in enumerate(s.objects):
                e.objects[o]["support"] = s.objects[(i+1)%3]
            self.assertEqual(evaluate(s, e).points, 0)
            for o in s.objects:
                e.objects[o]["support"] = "table"
            self.assertEqual(evaluate(s, e).points, 0)

    def test_bowls_must_be_upright(self):
        s, b, _ = fixture("stack-bowls")
        e = copy.deepcopy(b.final_evidence)
        e.objects[s.objects[0]]["upright"] = False
        self.assertEqual(evaluate(s, e).points, 0)

    def test_partial_tiers(self):
        for task, partial in (("pack-objects-into-box", [0,10,25,50,100]), ("hang-mugs", [0,15,40,100]), ("insert-tubes", [0,20,40,100])):
            s, b, _ = fixture(task)
            for count, expected in enumerate(partial):
                with self.subTest(task=task, count=count):
                    e = replace(b.final_evidence, objects={o: copy.deepcopy(b.final_evidence.objects[o]) if i < count else {} for i,o in enumerate(s.objects)})
                    self.assertEqual(evaluate(s, e).points, expected)

    def test_bad_insertion_depth_and_pack_orientation(self):
        for task, key in (("plug-in-charger", "depth_valid"), ("insert-tubes", "upright"), ("pack-objects-into-box", "orientation_valid")):
            s, b, _ = fixture(task)
            e = copy.deepcopy(b.final_evidence)
            e.objects[s.objects[0]][key] = False
            self.assertLess(evaluate(s, e).points, 100)

    def test_four_and_five_digit_tiers(self):
        for n, tiers in ((4, (0,5,15,30,100)), (5, (0,5,15,25,40,100))):
            s, b, _ = fixture("arrange-largest-number", digits_count=n)
            for count, expected in enumerate(tiers):
                e = replace(b.final_evidence, objects={o: b.final_evidence.objects[o] if i < count else {} for i,o in enumerate(s.objects)})
                self.assertEqual(evaluate(s, e).points, expected)
            e = copy.deepcopy(b.final_evidence)
            for o in s.objects:
                e.objects[o]["pad_index"] = 0
            self.assertEqual(evaluate(s, e).points, 0)

    def test_cover_order_and_partial_visibility(self):
        s, b, _ = fixture("cover-blocks")
        e = b.final_evidence
        for n, points in enumerate((5,15,30,100)):
            events = e.events[:3+n]
            uncovered = {a["object_id"] for a in events if a["kind"] == "uncover"}
            objects = {o: {"covered": o not in uncovered} for o in s.objects}
            self.assertEqual(evaluate(s, replace(e, events=events, objects=objects)).points, points)
        wrong = list(e.events)
        wrong[3], wrong[4] = wrong[4], wrong[3]
        self.assertEqual(evaluate(s, replace(e, events=tuple(wrong))).points, 0)
        wrong = list(e.events)
        wrong[0], wrong[1] = wrong[1], wrong[0]
        self.assertEqual(evaluate(s, replace(e, events=tuple(wrong))).points, 0)

    def test_press_exact_counts_and_confirm_protocol(self):
        s, b, _ = fixture("press-by-number")
        e = b.final_evidence
        self.assertEqual(evaluate(s, replace(e, events=e.events[:-1])).points, 0)
        self.assertEqual(evaluate(s, replace(e, events=e.events+(e.events[0],))).points, 0)
        with self.assertRaises(ValueError):
            evaluate(replace(s, truth={**s.truth, "protocol": "unknown"}), e)

    def test_classification_permutation_and_contamination(self):
        for task in ("classify-objects", "classify-objects-by-language"):
            s, b, _ = fixture(task)
            e = copy.deepcopy(b.final_evidence)
            baskets = s.truth["baskets"]
            for obj in e.objects.values():
                obj["container"] = baskets[(baskets.index(obj["container"])+1)%3]
            self.assertEqual(evaluate(s, e).points, 100 if task == "classify-objects" else 0)
            e = copy.deepcopy(b.final_evidence)
            e.objects["foreign-object"] = {"container": baskets[0], "settled": True}
            self.assertEqual(evaluate(s, e).points, 40)

    def test_stacking_toy_counts_groups_not_pieces(self):
        s, b, _ = fixture("play-stacking-toy")
        for complete, points in enumerate((0,10,30,60,100)):
            groups = list(s.truth["pegs"])[:complete]
            e = replace(b.final_evidence, objects={o: b.final_evidence.objects[o] if s.truth["groups"][o] in groups else {} for o in s.objects})
            self.assertEqual(evaluate(s, e).points, points)

    def test_align_requires_history_and_tool(self):
        s, b, _ = fixture("align-blocks")
        for flag in ("alignment_valid", "no_lift_entire_episode", "used_set_square"):
            e = replace(b.final_evidence, flags={**b.final_evidence.flags, flag: False})
            self.assertEqual(evaluate(s, e).points, 0)
        with self.assertRaises(ValueError):
            Action("place", s.objects[0], "row").validate(s)


class BoundaryTests(unittest.TestCase):
    def test_memory_masking_and_corrections(self):
        s, b, p = fixture("cover-blocks")
        s = replace(s, mask_instruction_after=1, corrections=((1, "Use the new parking area."),))
        session = Session(s, b, p)
        req = session.observe()["request"]
        self.assertNotIn("truth", req)
        self.assertNotIn("colors", req)
        session.decide(req)
        session.memory = "remembered by model"
        next_req = session.observe()["request"]
        self.assertIsNone(next_req["instruction"])
        self.assertEqual(next_req["memory"], "remembered by model")
        self.assertEqual(next_req["corrections"], ["Use the new parking area."])
        self.assertNotIn("source", next_req)

    def test_cover_redacts_hidden_attributes(self):
        s, b, p = fixture("cover-blocks")
        session = Session(s, b, p)
        req = session.observe()["request"]
        decision = session.decide(req)
        session.dispatch(decision["action"])
        after = session.observe()["request"]
        self.assertEqual(after["observation"]["objects"][s.objects[0]], {"occluded": True})

    def test_stale_observation_and_model_delay(self):
        s, b, p = fixture("stack-blocks")
        session = Session(s, b, p)
        req = session.observe()["request"]
        decision = session.decide(req)
        session.observation = replace(session.observation, captured_ns=time.monotonic_ns()-3_000_000_000)
        with self.assertRaises(ValueError):
            session.dispatch(decision["action"])
        self.assertEqual(b.index, 0)

    def test_unknown_command_never_retried(self):
        s, b, p = fixture("stack-blocks")
        session = Session(s, b, p)
        req = session.observe()["request"]
        action = session.decide(req)["action"]
        b.execute = lambda a, cmd, obs: Receipt(cmd, "unknown", False, obs.sequence+1)
        with self.assertRaises(RuntimeError):
            session.dispatch(action)
        self.assertEqual(len([e for e in session.events if e["kind"] == "command"]), 1)
        session.calls += 1
        with self.assertRaises(RuntimeError):
            session.dispatch(action)
        self.assertEqual(len([e for e in session.events if e["kind"] == "command"]), 1)

    def test_dispatch_exception_blocks_further_motion(self):
        s, b, p = fixture("stack-blocks")
        session = Session(s, b, p)
        action = session.decide(session.observe()["request"])["action"]
        def disconnected(*args):
            raise ConnectionError("lost after acceptance")
        b.execute = disconnected
        with self.assertRaises(ConnectionError):
            session.dispatch(action)
        session.calls += 1
        with self.assertRaises(RuntimeError):
            session.dispatch(action)

    def test_hardware_and_capability_guards(self):
        s, b, p = fixture("align-blocks")
        b.mode = "hardware"
        with self.assertRaises(ValueError):
            Session(s, b, p)
        b.mode, b.capabilities = "simulation", frozenset({"place"})
        with self.assertRaises(ValueError):
            Session(s, b, p)

    def test_decision_budget_and_episode_isolation(self):
        s, b, p = fixture("stack-blocks")
        session = Session(s, b, p, max_decisions=1)
        req = session.observe()["request"]
        session.decide(req)
        self.assertEqual(session.decide(req)["route"], "abort")
        self.assertEqual(len(p.requests), 1)
        session.memory = "old episode"
        s2, b2, p2 = fixture("stack-blocks", 1)
        self.assertEqual(Session(s2, b2, p2).memory, "")

    def test_invalid_response_and_memory_limits(self):
        s, b, p = fixture("stack-blocks")
        p.decide = lambda _: {"action": asdict(Action("home")), "memory": "12345"}
        session = Session(s, b, p, memory_chars=4)
        with self.assertRaises(ValueError):
            session.decide(session.observe()["request"])
        self.assertEqual(b.index, 0)

    def test_model_cannot_change_mid_episode(self):
        s, b, p = fixture("stack-blocks")
        session = Session(s, b, p)
        p.model_id = "different-model"
        with self.assertRaises(ValueError):
            session.decide(session.observe()["request"])
        self.assertEqual(b.index, 0)


class NativeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rtbench_tasks.graphs import build_all
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.graphs = build_all(cls.root / "graphs")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_thirteen_native_graphs(self):
        for task in TASKS:
            with self.subTest(task=task):
                s, b, p = fixture(task)
                report = run_episode(s, b, p, self.graphs/task, self.root/"runs"/task)
                self.assertTrue(report["workflow_completed"], report)
                self.assertTrue(report["task_success"])
                self.assertFalse(report["ranking_eligible"])
                self.assertEqual(len(report["checkpoints"]), len(b.actions))
                self.assertTrue(all(c["passed"] for c in report["checkpoints"]))
                self.assertTrue((self.root/"runs"/task/"trace"/"dag_trace.json").is_file())

    def test_failed_checkpoint_stops_graph(self):
        s, b, p = fixture("stack-blocks", 99)
        b.checkpoint = lambda: {"verified": False, "command_id": "untrusted"}
        report = run_episode(s, b, p, self.graphs/s.task_id, self.root/"failed")
        self.assertFalse(report["workflow_completed"])
        self.assertEqual(b.index, 1)
        self.assertFalse(report["checkpoints"][0]["passed"])

    def test_wrong_skill_action_terminates(self):
        s, b, _ = fixture("align-blocks", 88)
        p = ReplayPolicy([Action("place", s.objects[0], "row")])
        report = run_episode(s, b, p, self.graphs/s.task_id, self.root/"invalid")
        self.assertFalse(report["workflow_completed"])
        self.assertEqual(b.index, 0)

    def test_no_overwriting_a_trial(self):
        s, b, p = fixture("stack-blocks", 123)
        out = self.root/"existing"
        out.mkdir()
        with self.assertRaises(FileExistsError):
            run_episode(s, b, p, self.graphs/s.task_id, out)

    def test_wrong_task_graph_rejected_before_reset(self):
        s, b, p = fixture("stack-blocks", 124)
        with self.assertRaises(ValueError):
            run_episode(s, b, p, self.graphs/"cover-blocks", self.root/"wrong-graph")


if __name__ == "__main__":
    unittest.main()
