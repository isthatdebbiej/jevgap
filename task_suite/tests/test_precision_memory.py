import unittest
from rtbench_tasks.precision_memory import CueSchedule, DISTRACTOR_TRANSFERS, INITIAL_JOB, task_spec


class PrecisionMemoryTests(unittest.TestCase):
    def test_instruction_hidden_and_work_not_decisions_advances_cues(self):
        schedule = CueSchedule()
        self.assertEqual(schedule.cue(), INITIAL_JOB)
        for obj, target in DISTRACTOR_TRANSFERS:
            first = schedule.cue()
            self.assertEqual(first, schedule.cue())
            self.assertNotIn("90 degrees", first)
            schedule.verified_transfer(obj, target, verified=True)
        self.assertEqual(schedule.cue(), "Execute the remembered job.")
        self.assertEqual(CueSchedule().cue(), INITIAL_JOB)

    def test_unverified_or_wrong_transfer_never_advances(self):
        schedule = CueSchedule()
        schedule.cue()
        for args in [("D", "D2", False), ("A", "T2", True), ("E", "E2", True)]:
            with self.assertRaises(ValueError):
                schedule.verified_transfer(args[0], args[1], verified=args[2])
            self.assertEqual(schedule.transfers, 0)

    def test_correction_at_transfer_two_once(self):
        schedule = CueSchedule(correction=True)
        schedule.cue()
        for obj, target in DISTRACTOR_TRANSFERS[:2]:
            schedule.verified_transfer(obj, target, verified=True)
        with self.assertRaises(ValueError):
            schedule.verified_transfer(*DISTRACTOR_TRANSFERS[2], verified=True)
        self.assertIn("Swap A's and B's", schedule.cue())
        self.assertNotIn("Swap", schedule.cue())

    def test_sdk_task_does_not_repeat_hidden_assignment_and_caps_time(self):
        task = task_spec()
        self.assertEqual(task.max_rollout_time, 450)
        self.assertNotIn("T2", task.instruction)
        self.assertNotIn("90", task.instruction)
