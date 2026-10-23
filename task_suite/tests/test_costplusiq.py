"""Offline provider contracts: no API calls, real credentials or robot connections."""
import copy
import io
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from rtbench_tasks.config import Experiment, preflight
from rtbench_tasks.costplusiq import CostPlusIQPolicy
from rtbench_tasks.experiment import initialize
from rtbench_tasks.model_profiles import MODELS, openmodel_config
from rtbench_tasks.responses import ResponsesPolicy, make_policy, validate_config


class CostPlusIQTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = self.root / "test.key"
        self.key.write_text("\ufefftest-only-credential\n", encoding="utf-8")
        self.config = openmodel_config(key_file=self.key, budget_ledger=self.root / "budget.sqlite")
        self.config.update(budget_usd=2, reservation_usd=1, max_output_tokens=100)
        self.request = {"instruction": None, "memory": "retain this", "skills": {"finish": "done"}, "observation": {}}
        self.answer = {"action": {"skill": "finish", "object_id": "", "target_id": "", "orientation": ""}, "memory": "retain this"}

    def response(self):
        return {"model": self.config["model_id"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(self.answer)}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}

    def test_http_endpoint_auth_schema_statelessness_and_normalized_usage(self):
        sent = []
        def send(request, timeout):
            sent.append((request, timeout))
            return io.BytesIO(json.dumps(self.response()).encode())
        with patch("rtbench_tasks.responses.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = send
            policy = make_policy(self.config, live=True)
            self.assertEqual(policy.decide(self.request), self.answer)
            self.assertEqual(policy.decide(self.request), self.answer)
        request, timeout = sent[0]
        self.assertEqual(request.full_url, "https://api.costplusiq.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only-credential")
        self.assertEqual(timeout, 60)
        payload = json.loads(request.data)
        self.assertEqual(payload, json.loads(sent[1][0].data))
        self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user"])
        self.assertEqual(json.loads(payload["messages"][1]["content"]), self.request)
        self.assertEqual(payload["max_tokens"], 100)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertNotIn("input", payload)
        self.assertNotIn("store", payload)
        schema = payload["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["schema"]["properties"]["action"]["properties"]["skill"]["enum"], ["finish"])
        self.assertEqual(policy.calls[0]["usage"], {"input_tokens": 50, "output_tokens": 10})
        self.assertNotIn("test-only-credential", json.dumps(policy.calls) + request.data.decode())

    def test_truncated_refused_wrong_model_invalid_actions_and_usage_fail_closed(self):
        bad = []
        r = self.response(); r["choices"][0]["finish_reason"] = "length"; bad.append(r)
        r = self.response(); r["choices"][0]["message"]["refusal"] = "no"; bad.append(r)
        r = self.response(); r["model"] = "different"; bad.append(r)
        r = self.response(); r["choices"][0]["message"]["content"] = "not JSON"; bad.append(r)
        r = self.response(); r["choices"][0]["message"]["tool_calls"] = [{}]; bad.append(r)
        r = self.response(); r["choices"] = []; bad.append(r)
        r = self.response(); r["usage"] = {}; bad.append(r)
        r = self.response(); r["usage"]["completion_tokens"] = 101; bad.append(r)
        r = self.response(); r["usage"]["prompt_tokens"] = True; bad.append(r)
        r = self.response(); a = copy.deepcopy(self.answer); a["action"]["skill"] = "unknown"; r["choices"][0]["message"]["content"] = json.dumps(a); bad.append(r)
        for i, result in enumerate(bad):
            with self.subTest(case=i):
                cfg = {**self.config, "budget_ledger": str(self.root / f"bad-{i}.sqlite")}
                policy = make_policy(cfg, transport=lambda _: result)
                with self.assertRaisesRegex(RuntimeError, "reservation retained"):
                    policy.decide(self.request)
                with closing(sqlite3.connect(cfg["budget_ledger"])) as db:
                    self.assertEqual(db.execute("SELECT status, reservation FROM task_calls").fetchone(), ("reserved", 1))

    def test_failed_calls_share_budget_without_retry_or_secret_logs(self):
        attempts = []
        def fail(payload):
            attempts.append(payload)
            raise urllib.error.HTTPError(CostPlusIQPolicy.endpoint, 401, "test-only-credential", {}, None)
        for _ in range(2):
            policy = make_policy(self.config, transport=fail)
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                policy.decide(self.request)
            self.assertNotIn("test-only-credential", str(caught.exception) + json.dumps(policy.calls))
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            make_policy(self.config, transport=fail).decide(self.request)
        self.assertEqual(len(attempts), 2)

    def test_oversized_input_no_reservation_and_live_opt_in(self):
        with self.assertRaisesRegex(ValueError, "--live"):
            make_policy(self.config)
        policy = make_policy({**self.config, "max_input_bytes": 1}, transport=lambda _: self.response())
        with self.assertRaisesRegex(ValueError, "input exceeds"):
            policy.decide(self.request)
        self.assertFalse(Path(self.config["budget_ledger"]).exists())

    def test_model_choices_reasoning_and_adapter_isolation(self):
        for model in MODELS:
            cfg = {**self.config, "model_id": model, "enable_thinking": False}
            p = make_policy(cfg, transport=lambda _: None)
            self.assertIsInstance(p, CostPlusIQPolicy)
            self.assertEqual(p._build_payload(self.request)["chat_template_kwargs"], {"enable_thinking": False})
        for change in ({"api_key": "inline"}, {"max_output_tokens": 32769}, {"enable_thinking": "false"},
                       {"provider": "unknown"}, {"reasoning_effort": "max"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_config({**self.config, **change})
        with self.assertRaisesRegex(ValueError, "adapter"):
            ResponsesPolicy(self.config, transport=lambda _: None)

    def test_astra_payload_and_endpoint_preserved(self):
        cfg = {k: v for k, v in self.config.items() if k != "provider"}
        cfg["model_id"] = "gpt-6-astra"
        result = {"model": cfg["model_id"], "status": "completed", "usage": {"input_tokens": 50, "output_tokens": 10},
                  "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(self.answer)}]}]}
        policy = make_policy(cfg, transport=lambda _: result)
        self.assertIs(type(policy), ResponsesPolicy)
        self.assertEqual(policy.endpoint, "https://api.openai.com/v1/responses")
        payload = policy._build_payload(self.request)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertFalse(payload["store"])
        self.assertNotIn("messages", payload)
        self.assertEqual(policy.decide(self.request), self.answer)

    def test_init_adds_profile_and_preflight_accepts_provider(self):
        root = initialize(self.root / "configs", self.root / "missing-gap")
        original = json.loads((root / "se3.local.json").read_text())
        self.assertEqual(original["model"]["provider"], "openai-responses")
        p = root / "se3-openmodels.local.json"
        profile = json.loads(p.read_text())
        self.assertEqual(profile["model"]["model_id"], MODELS[0])
        self.assertEqual(profile["model"]["budget_usd"], 0)
        profile["model"] = self.config
        p.write_text(json.dumps(profile))
        with patch("rtbench_tasks.responses.urllib.request.build_opener") as opener:
            status = preflight(Experiment(p))
        opener.assert_not_called()
        self.assertFalse(any("model" in blocker for blocker in status["blockers"]), status)
        self.assertFalse(status["hardware_validated"])


if __name__ == "__main__":
    unittest.main()
