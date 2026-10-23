import signal
import unittest
from unittest.mock import Mock, patch

from rtbench_tasks.upstream_worker import cap_deadline


class DeadlineTests(unittest.TestCase):
    def test_native_1000_second_reset_cannot_extend_450_seconds(self):
        alarm = Mock(return_value=100)
        with patch.object(signal, "alarm", alarm, create=True), \
             patch("rtbench_tasks.upstream_worker.time.monotonic", side_effect=[10, 60, 461]):
            with cap_deadline(450):
                signal.alarm(450)
                signal.alarm(0)
                signal.alarm(1000)
                with self.assertRaises(TimeoutError):
                    signal.alarm(1000)
            self.assertIs(signal.alarm, alarm)
        self.assertEqual([call.args[0] for call in alarm.call_args_list], [450, 0, 400, 0])

    def test_exception_restores_native_alarm(self):
        alarm = Mock()
        with patch.object(signal, "alarm", alarm, create=True):
            with self.assertRaises(ValueError):
                with cap_deadline(450):
                    raise ValueError("failure")
            self.assertIs(signal.alarm, alarm)
        alarm.assert_called_once_with(0)
