import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PIL import Image

import os
if os.name != 'posix':
    raise unittest.SkipTest('SE3 ACT requires Linux/WSL')

from rtbench_tasks.act_agent import Robot, prompt
from rtbench_tasks.act_native import GapTools, CapEnv
from rtbench_tasks.act_run import load_task, task_spec


class Harness:
    def __init__(self, path):
        self.path, self.commands = path, []
        Image.new("RGB", (640,360), "gray").save(path)
        self.stamp, self.identity, self.budget = 10.0, "test", 450
        self.age = 0

    def status(self):
        return {"ok":True,"phase":"rollout","elapsed_s":1,"budget_s":self.budget,
                "episode_id":self.identity,"observation_received_ns":time.monotonic_ns()-int(self.age*1e9),
                "arms":{name:{"measured_timestamp_s":self.stamp,"offset_m":[0,0,0],"rpy_deg":[0,0,0]} for name in ("left","right")}}

    def cameras(self):
        return {"ok":True,"episode_id":self.identity,"cameras":{name:{"path":str(self.path),"timestamp":self.stamp} for name in ("topdown","wrist_left","wrist_right")}}

    def move(self, **kwargs):
        self.commands.append(kwargs)
        return {"ok":True}

    def end_episode(self):
        return {"ok":True}

    def hold(self):
        return {"ok":True}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.h = Harness(self.root / "frame.jpg")
        self.robot = Robot(self.h, self.root / "robot")

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_cameras_reach_model_and_originals_are_saved(self):
        messages = prompt(self.robot, "test")
        self.assertEqual(sum(x["type"]=="image_url" for x in messages[0]["content"]), 3)
        self.assertEqual(len(list((self.root/"robot").rglob("*.jpg"))), 3)
        self.assertLess(len(json.dumps(messages)), 100000)

    def test_bad_motion_never_reaches_controller(self):
        for args in ({"arm":"left", "dx":0.1}, {"arm":"left","dx":float("nan")},
                     {"arm":"left", "yaw":31}, {"arm":"other"}, {"arm":"left", "dx":True}):
            with self.assertRaises(ValueError):
                self.robot.call("robot_move", args)
        self.assertEqual(self.h.commands, [])

    def test_wrong_episode_stale_or_overlong_rollout_blocks(self):
        self.robot.status()
        self.h.identity = "replacement"
        with self.assertRaises(RuntimeError): self.robot.status()
        self.h.identity = "test"
        self.h.age = 4
        with self.assertRaises(TimeoutError): self.robot.status()
        self.h.age = 0
        self.h.budget = 600
        with self.assertRaises(TimeoutError): self.robot.status()

    def test_model_chooses_real_tool_without_semantic_driver(self):
        client = SimpleNamespace(model_id="Qwen/Qwen3.8-27B", config={}, query=Mock(return_value={
            "content":json.dumps({"tool":"robot_move","arguments":{"arm":"left","dx":0.01},"memory":"remember"})}))
        loop = GapTools(self.robot, client, "test")
        self.assertEqual(loop.step(), {"route":"again"})
        self.assertEqual(self.h.commands, [{"arm":"left","dx":0.01}])
        self.assertEqual(loop.memory, "remember")

    def test_native_code_finish_is_not_task_success(self):
        env = CapEnv(self.robot, "test")
        env.reset()
        _, reward, terminal, _, info = env.step("robot.call('robot_end_episode', {})")
        self.assertTrue(terminal)
        self.assertFalse(info["task_completed"])
        self.assertEqual(reward, 0)
        self.assertIn("terminated episode", info["stderr"])
        with self.assertRaises(RuntimeError): env.reset()

    def test_all_local_tasks_have_real_sdk_specs_but_memory_not_static(self):
        from rtbench_tasks.catalog import TASKS
        for task in TASKS.values():
            spec = task_spec({"name":task.id,"instruction":task.instruction,"reset_instruction":"prepare props",
                              "success_question":"Did the task succeed?"})
            self.assertEqual(spec.max_rollout_time,450)
        p=self.root/"task.json"
        p.write_text(json.dumps({"name":"precision-memory-delayed","instruction":"hidden job",
                                "reset_instruction":"prepare","success_question":"success?"}))
        for task_id in ("press-by-number", "classify-objects-by-language"):
            blocked=self.root/(task_id+".json")
            blocked.write_text(json.dumps({"name":task_id,"instruction":TASKS[task_id].instruction,
                                          "reset_instruction":"prepare","success_question":"success?"}))
            with self.assertRaises(ValueError): load_task(blocked)
        data=load_task(p)
        self.assertNotIn("hidden job", task_spec(data).instruction)

    def test_service_uses_actual_act_policy_and_450_second_task(self):
        from rtbench_tasks.act_run import serve
        from se3labs.sdk.examples.act_harness.policy import ActHarnessPolicy
        task=self.root/"task.json"
        task.write_text(json.dumps({"name":"test","instruction":"observe",
                                   "reset_instruction":"prepare","success_question":"success?"}))
        args=SimpleNamespace(live=True,task=task,socket=str(self.root/"act.sock"),
                             output=self.root/"service",auth_file=None,station="yam-test",address="127.0.0.1:1")
        def fake_serve(station,address,request):
            self.assertIsInstance(request.policy,ActHarnessPolicy)
            self.assertEqual(request.task.max_rollout_time,450)
            self.assertEqual(request.episodes,1)
            self.assertFalse(request.policy.keyboard)
            return SimpleNamespace(state="SUCCEEDED",close_reason="COMPLETED",episodes=1,errors=[],results=[])
        with patch("se3labs.sdk.eval_client.serve_policy",side_effect=fake_serve):
            serve(args)
        self.assertTrue((args.output/"se3-session.json").is_file())


    def test_model_graph_rejects_cycles_dangling_and_unknown_tools(self):
        from rtbench_tasks.act_gap import validate_graph
        good={"memory":"", "start":"step", "nodes":[{"id":"step","tool":"robot_status","arguments":{},"on_success":"observe","on_failure":"abort"}]}
        self.assertEqual(validate_graph(good),good)
        for field,value in (("on_success","step"),("on_success","missing"),("tool","shell")):
            bad=copy.deepcopy(good);bad["nodes"][0][field]=value
            with self.assertRaises(ValueError): validate_graph(bad)

    def test_real_sdk_scoring_roundtrip_and_uncommissioned_gate(self):
        from rtbench_tasks.act_prepare import build
        from rtbench_tasks.act_run import serve
        from se3labs.interface.wire import policy_session_pb2 as pb
        workspace=Path(__file__).resolve().parents[2]
        packet=self.root/'packet';build(workspace,packet)
        args=SimpleNamespace(live=True,task=packet/'tasks/press-by-number.json',socket=str(self.root/'scored.sock'),
                             output=self.root/'scored-service',auth_file=None,station='yam-test',address='127.0.0.1:1',packet=packet,commissioning_trial=False)
        with patch('se3labs.sdk.eval_client.serve_policy') as launch:
            with self.assertRaises(ValueError):serve(args)
            launch.assert_not_called()
        args.commissioning_trial=True
        def fake_serve(station,address,request):
            ep=pb.EpisodeResult(episode_id='ep_test',scored=True,success=True)
            for item in request.task.scoring.all_items:
                out=ep.items.add();out.item.key=item.key
                if item.key=='task_success':out.yes=True
                elif item.key=='general_progress':out.choice=1
                else:out.choice=1 if item.key=='q_0_0' else 2
            return SimpleNamespace(state='SUCCEEDED',close_reason='COMPLETED',episodes=1,errors=[],results=[ep])
        with patch('se3labs.sdk.eval_client.serve_policy',side_effect=fake_serve):serve(args)
        result=json.loads((args.output/'study-scores.json').read_text())[0]
        self.assertEqual(result['general_progress'],100)
        self.assertEqual(result['breakdown_quality'],85)
        self.assertTrue(json.loads((args.output/'manifest.json').read_text())['commissioning_trial'])
