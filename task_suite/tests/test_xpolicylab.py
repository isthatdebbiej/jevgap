import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from se3labs.interface.eval.arm import MotorizedArm_JointPose
from se3labs.interface.eval.station import Station_JointPose

from se3labs.sdk.examples.hold_still import HOLD_STILL_TASK
from rtbench_tasks.xpolicylab import run_deployment


class XPolicyLabTests(unittest.TestCase):
    def pose(self):
        return Station_JointPose({name: MotorizedArm_JointPose(np.zeros(6, np.float32), np.ones(1, np.float32))
                                  for name in ("left", "right")})

    def test_both_harnesses_use_same_bridge_and_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            for harness in ("native-gap", "cap"):
                report = SimpleNamespace(state="SUCCEEDED", close_reason="COMPLETED",
                                         episodes=1, steps=3, errors=[], results=[])
                bridge = Mock(return_value=report)
                deploy, client = Mock(), SimpleNamespace()
                output = Path(tmp) / harness
                actual = run_deployment(deploy, client, harness=harness,
                    task=HOLD_STILL_TASK, start_pose=self.pose(),
                    frequency=10, output=output, evaluate=bridge)
                self.assertIs(actual, report)
                args, kwargs = bridge.call_args
                self.assertEqual(args, (deploy, client))
                self.assertEqual(kwargs["task"].max_rollout_time, 450)
                self.assertEqual(kwargs["station_id"], "se3-labs-yam-2")
                self.assertEqual(kwargs["address"], "100.107.161.92:7443")
                self.assertEqual(kwargs["episodes"], 1)
                self.assertTrue((output / "se3-session.json").exists())

    def test_over_budget_rejected_before_connection(self):
        bridge = Mock()
        with self.assertRaises(ValueError):
            run_deployment(Mock(), object(), harness="cap", task=HOLD_STILL_TASK,
                           start_pose=None, frequency=10, output="unused",
                           episode_timeout_s=451, evaluate=bridge)
        bridge.assert_not_called()

    def test_invalid_pose_and_rate_fail_before_connection(self):
        for pose, frequency in [(None, 10), (self.pose(), 101)]:
            bridge = Mock()
            with self.assertRaises(ValueError):
                run_deployment(Mock(), object(), harness="cap", task=HOLD_STILL_TASK,
                               start_pose=pose, frequency=frequency, output="unused", evaluate=bridge)
            bridge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
