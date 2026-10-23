import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from rtbench_tasks.act_fixture import FixtureGate, confirm
from rtbench_tasks.act_cues import CueFeed, confirm as transfer
from rtbench_tasks.precision_memory import DISTRACTOR_TRANSFERS


class FixtureTests(unittest.TestCase):
    def test_withholds_old_decision_until_locked_and_reobserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=CueFeed(tmp,"episode",variant="moving-cube")
            feed()
            for i,(obj,target) in enumerate(DISTRACTOR_TRANSFERS,1):
                transfer(tmp,"episode",i,obj,target)
                feed()
            gate=feed.motion_guard
            self.assertEqual(gate.stage,"armed")
            harness=SimpleNamespace(hold=Mock(return_value={"ok":True}),status=lambda:{"ok":True,"phase":"rollout",
                "episode_id":"episode","arms":{"left":{"measured_timestamp_s":20}}})
            robot=SimpleNamespace(harness=harness,journal=Mock())
            withheld=gate.before_motion(robot,"robot_move",{"arm":"left","dx":0.01})
            self.assertFalse(withheld["command_executed"])
            self.assertTrue((Path(tmp)/"fixture-request.json").exists())
            confirm(tmp,harness,arm_clear=True,locked=True)
            self.assertTrue(gate.before_motion(robot,"robot_move",{})["refresh_observation"])
            with self.assertRaises(ValueError): gate.observed(19)
            gate.observed(21)
            self.assertIsNone(gate.before_motion(robot,"robot_move",{}))
            harness.hold.assert_called_once()

    def test_alternate_history_has_same_later_visible_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=CueFeed(Path(tmp)/"first","e1")
            other=CueFeed(Path(tmp)/"other","e2",variant="different-history")
            self.assertNotEqual(first(),other())
            self.assertEqual(first(),other())
