import tempfile
import unittest
from pathlib import Path
from rtbench_tasks.act_cues import CueFeed, confirm
from rtbench_tasks.precision_memory import DISTRACTOR_TRANSFERS


class CueTests(unittest.TestCase):
    def test_job_only_once_correction_once_no_unverified_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=CueFeed(tmp,"episode",correction=True)
            self.assertIn("A at T2",feed())
            for index,(obj,target) in enumerate(DISTRACTOR_TRANSFERS,1):
                self.assertNotIn("A at T2",feed())
                self.assertEqual(feed.schedule.transfers,index-1)
                confirm(tmp,"episode",index,obj,target)
                cue=feed()
                if index==2:
                    self.assertIn("Swap",cue)
                    self.assertNotIn("Swap",feed())
            self.assertEqual(feed(),"Execute the remembered job.")

    def test_wrong_episode_and_duplicates_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=CueFeed(tmp,"new")
            feed()
            confirm(tmp,"old",1,"D","D2")
            with self.assertRaises(ValueError): feed()
            with self.assertRaises(FileExistsError): confirm(tmp,"new",1,"D","D2")
