"""Stateless OpenAI Responses adapter for semantic actions and explicit memory."""
import json
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from .config import positive

ENDPOINT = "https://api.openai.com/v1/responses"
FIELDS = ("skill", "object_id", "target_id", "orientation")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_config(config):
    allowed = {"provider", "model_id", "key_file", "budget_ledger", "budget_usd", "reservation_usd",
               "max_output_tokens", "max_input_bytes", "timeout_s", "reasoning_effort", "accepted_response_models"}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError("unknown model fields; credentials must be supplied by key_file")
    required = ("model_id", "key_file", "budget_ledger", "budget_usd", "reservation_usd")
    if any(not config.get(k) for k in required):
        raise ValueError("model requires model_id, key_file, budget_ledger, budget_usd and reservation_usd")
    for key in ("model_id", "key_file", "budget_ledger"):
        if not isinstance(config[key], str) or "REPLACE" in config[key]:
            raise ValueError(f"configure model.{key}")
    accepted = config.get("accepted_response_models", [config["model_id"]])
    if not isinstance(accepted, list) or not accepted or any(not isinstance(m, str) or not m for m in accepted):
        raise ValueError("accepted_response_models must contain explicit model ids")
    for key in ("budget_usd", "reservation_usd"):
        positive(config[key], key)
    if config["reservation_usd"] > config["budget_usd"]:
        raise ValueError("reservation_usd exceeds budget_usd")
    for key, default in (("max_output_tokens", 2048), ("max_input_bytes", 64000)):
        n = config.get(key, default)
        if type(n) is not int or not 1 <= n <= 100000:
            raise ValueError(f"invalid {key}")
    positive(config.get("timeout_s", 60), "model.timeout_s")


class ResponsesPolicy:
    def __init__(self, config, *, live=False, transport=None):
        validate_config(config)
        if not live and transport is None:
            raise ValueError("model requests require --live")
        self.config = dict(config)
        self.model_id = config["model_id"]
        self.calls = []
        self._transport = transport or self._send

    def _reserve(self):
        p = Path(self.config["budget_ledger"])
        p.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(p, timeout=30)) as db, db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables - {"task_calls"}:
                raise ValueError("use a dedicated task-suite budget ledger; existing ledger schema differs")
            db.execute("CREATE TABLE IF NOT EXISTS task_calls (id INTEGER PRIMARY KEY, model TEXT, reservation REAL, status TEXT, usage TEXT)")
            db.execute("BEGIN IMMEDIATE")
            total = db.execute("SELECT COALESCE(SUM(reservation),0) FROM task_calls").fetchone()[0]
            if total + self.config["reservation_usd"] > self.config["budget_usd"] + 1e-9:
                raise RuntimeError("task-model reservation budget exhausted")
            return db.execute("INSERT INTO task_calls(model,reservation,status) VALUES (?,?,?)",
                              (self.model_id, self.config["reservation_usd"], "reserved")).lastrowid

    def _send(self, payload):
        key = Path(self.config["key_file"]).read_text(encoding="utf-8-sig").strip()
        if not key or any(c.isspace() for c in key):
            raise ValueError("invalid credential file")
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload, allow_nan=False).encode(),
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=self.config.get("timeout_s", 60)) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("oversized response")
        return json.loads(raw)

    def decide(self, request):
        text = json.dumps(request, allow_nan=False)
        if len(text.encode()) > self.config.get("max_input_bytes", 64000):
            raise ValueError("policy input exceeds configured byte limit")
        schema = {"type": "object", "additionalProperties": False, "required": ["action", "memory"],
                  "properties": {"memory": {"type": "string"}, "action": {
                      "type": "object", "additionalProperties": False, "required": list(FIELDS),
                      "properties": {k: {"type": "string"} for k in FIELDS}}}}
        schema["properties"]["action"]["properties"]["skill"]["enum"] = list(request["skills"])
        payload = {"model": self.model_id, "store": False,
                   "instructions": "Choose one supported robot action from the supplied observation and explicit memory. Preserve needed task information in memory. Use no hidden conversation. Return finish only when the task is done; use abort when it cannot proceed. Never assert measured execution success.",
                   "input": text, "max_output_tokens": self.config.get("max_output_tokens", 2048),
                   "text": {"format": {"type": "json_schema", "name": "robot_action_memory", "strict": True, "schema": schema}}}
        if self.config.get("reasoning_effort"):
            payload["reasoning"] = {"effort": self.config["reasoning_effort"]}
        call_id = self._reserve()
        start = time.monotonic_ns()
        try:
            result = self._transport(payload)
            accepted = self.config.get("accepted_response_models", [self.model_id])
            if result.get("model") not in accepted or result.get("status") != "completed":
                raise ValueError("unexpected model or incomplete response")
            parts = [part for item in result.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
            if any(part.get("type") == "refusal" for part in parts):
                raise ValueError("model refused the request")
            response = json.loads("".join(p["text"] for p in parts if p.get("type") == "output_text"))
            if not isinstance(response, dict) or set(response) != {"action", "memory"}:
                raise ValueError("invalid action-memory response")
            if not isinstance(response["memory"], str) or not isinstance(response["action"], dict) or set(response["action"]) != set(FIELDS):
                raise ValueError("invalid action-memory fields")
            if any(not isinstance(v, str) for v in response["action"].values()):
                raise ValueError("action fields must be strings")
            usage = result.get("usage", {})
            if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
                raise ValueError("invalid token usage")
            if usage["output_tokens"] > payload["max_output_tokens"]:
                raise ValueError("output token limit exceeded")
            record = {"call_id": call_id, "response_model": result["model"], "usage": usage,
                      "latency_ns": time.monotonic_ns() - start, "reserved_usd": self.config["reservation_usd"]}
            self.calls.append(record)
            with closing(sqlite3.connect(self.config["budget_ledger"], timeout=30)) as db, db:
                db.execute("UPDATE task_calls SET status='completed',usage=? WHERE id=?", (json.dumps(usage), call_id))
            return response
        except Exception as exc:
            # No automatic retries, remote bodies, keys or raw exception messages in logs.
            kind = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            self.calls.append({"call_id": call_id, "error_type": kind, "reserved_usd": self.config["reservation_usd"]})
            raise RuntimeError(f"model call failed ({kind}); reservation retained") from None
