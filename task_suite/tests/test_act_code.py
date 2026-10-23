import unittest
from rtbench_tasks.act_code import compile_policy, SAFE_BUILTINS


class CodeTests(unittest.TestCase):
    def test_rejects_private_file_import_and_deadline_catching(self):
        for code in ("import os", "robot.harness.send('move left 1 0 0')", "x=robot.call.__globals__",
                     "x=__builtins__", "robot=1", "try:\n pass\nexcept:\n pass", "with open('x') as f: pass"):
            with self.subTest(code=code), self.assertRaises(ValueError): compile_policy(code)
        self.assertNotIn("open",SAFE_BUILTINS)
        self.assertNotIn("eval",SAFE_BUILTINS)
        self.assertNotIn("__import__",SAFE_BUILTINS)

    def test_persistent_computation_and_robot_api(self):
        calls=[]
        class Robot:
            def call(self,name,args): calls.append((name,args))
        ns={"robot":Robot(),"__builtins__":SAFE_BUILTINS}
        exec(compile_policy("job={'A':'T2'}\npositions=[]\nfor i in range(2): positions.append(i)"),ns)
        exec(compile_policy("robot.call('robot_status', {})\nassert job.get('A')=='T2'\nassert positions==[0,1]"),ns)
        self.assertEqual(calls,[("robot_status",{})])
