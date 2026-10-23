import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from rtbench_tasks.cap_costplusiq import NativeClient
from rtbench_tasks.model_profiles import openmodel_config


class NativeClientTests(unittest.TestCase):
    def test_native_code_and_images_preserved_with_shared_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            config = openmodel_config()
            config.update(key_file="unused-key", budget_ledger=str(Path(directory)/"budget.sqlite"),
                          budget_usd=0.1, reservation_usd=0.1)
            seen = []
            def transport(payload):
                seen.append(payload)
                return {"model": config["model_id"], "choices": [{"finish_reason": "stop", "message": {"content": "```python\nrobot.observe()\n```"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 8}}
            client = NativeClient(config, transport=transport)
            prompt = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,diagnostic"}}]}]
            answer = client.query(SimpleNamespace(model=client.model_id), prompt)
            self.assertIn("robot.observe", answer["content"])
            self.assertEqual(seen[0]["messages"], prompt)
            self.assertEqual(seen[0]["reasoning_effort"], "low")
            second = NativeClient(config, transport=transport)
            with self.assertRaises(RuntimeError):
                second.query(SimpleNamespace(model=client.model_id), prompt)
            self.assertEqual(len(seen), 1)

    def test_wrong_model_rejected_without_request(self):
        config = openmodel_config()
        config.update(key_file="unused-key", budget_ledger="unused", budget_usd=1, reservation_usd=1)
        client = NativeClient(config, transport=lambda p: self.fail("must not call provider"))
        with self.assertRaises(ValueError):
            client.query(SimpleNamespace(model="other-model"), [])
