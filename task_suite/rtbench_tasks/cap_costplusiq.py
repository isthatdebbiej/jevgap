"""Bounded CostPlusIQ transport for the native CaP-X generation loop.

Uses the same key-file/reservation contract as GaP; no native policy logic is
replaced. The context explicitly registers the configured vision model and
replaces only HTTP queries, eliminating the native unbounded retry loop.
"""
import json
import time
import sqlite3
from contextlib import contextmanager, closing
from unittest.mock import patch

from .costplusiq import CostPlusIQPolicy
from .model_profiles import MODELS


class NativeClient(CostPlusIQPolicy):
    def query(self, args, prompt):
        if args.model != self.model_id:
            raise ValueError("CaP attempted to change the shared model")
        if len(json.dumps(prompt, ensure_ascii=False).encode()) > self.config.get("max_input_bytes", 64000):
            raise ValueError("CaP prompt exceeds shared input budget")
        payload = {"model": self.model_id, "messages": prompt,
                   "max_tokens": self.config.get("max_output_tokens", 2048),
                   "reasoning_effort": self.config.get("reasoning_effort", "low")}
        if "enable_thinking" in self.config:
            payload["chat_template_kwargs"] = {"enable_thinking": self.config["enable_thinking"]}
        call_id = self._reserve()
        started = time.monotonic_ns()
        try:
            body = self._transport(payload)
            if body.get("model") not in self.config.get("accepted_response_models", [self.model_id]):
                raise ValueError("unexpected response model")
            choices = body.get("choices", [])
            if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
                raise ValueError("incomplete native code response")
            message = choices[0]["message"]
            if message.get("refusal") or message.get("tool_calls") or not isinstance(message.get("content"), str):
                raise ValueError("invalid native code response")
            usage = body.get("usage", {})
            if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("prompt_tokens", "completion_tokens")):
                raise ValueError("invalid usage")
            if usage["completion_tokens"] > payload["max_tokens"]:
                raise ValueError("output token budget exceeded")
            self.calls.append({"call_id": call_id, "usage": usage,
                               "latency_ns": time.monotonic_ns() - started})
            with closing(sqlite3.connect(self.config["budget_ledger"])) as db, db:
                db.execute("UPDATE task_calls SET status='completed',usage=? WHERE id=?", (json.dumps(usage), call_id))
            # Reservations are retained on success and failure: no cost estimate
            # silently releases budget or permits additional requests.
            return {"content": message["content"], "reasoning": message.get("reasoning")}
        except Exception as exc:
            self.calls.append({"call_id": call_id, "error_type": type(exc).__name__})
            raise RuntimeError(f"CaP model request failed ({type(exc).__name__})") from None


@contextmanager
def native_transport(client):
    from capx.llm import client as native
    from capx.envs import trial
    if client.model_id not in MODELS:
        raise ValueError("vision support must be verified for this model")
    added = client.model_id not in native.VLM_MODELS
    if added:
        native.VLM_MODELS.append(client.model_id)
    try:
        with patch.object(native, "query_model", client.query), patch.object(trial, "_query_model", client.query):
            yield
    finally:
        if added:
            native.VLM_MODELS.remove(client.model_id)
