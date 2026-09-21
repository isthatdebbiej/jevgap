"""OpenAI Astra baseline: same state, instructions and decision enum as Jev."""

import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request
from jev_provider import CRITERIA, INSTRUCTIONS, NoRedirect

MODEL = "gpt-6-astra"
ENDPOINT = "https://api.openai.com/v1/responses"
CAP = 100.0
RESERVATION = 0.35  # bounded 16KB input plus 2048 output tokens, including cache writes


def reserve(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as db:
        db.execute("CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, charge REAL, status TEXT, detail TEXT)")
        db.execute("BEGIN IMMEDIATE")
        spent = db.execute("SELECT COALESCE(SUM(charge),0) FROM calls").fetchone()[0]
        if spent + RESERVATION > CAP:
            raise RuntimeError("Astra $100 experiment budget exhausted")
        return db.execute("INSERT INTO calls(charge,status) VALUES (?,?)", (RESERVATION, "reserved")).lastrowid


def evaluate(state):
    prompt = json.dumps({"instructions": INSTRUCTIONS, "criteria": CRITERIA, "state": state}, allow_nan=False)
    if len(prompt.encode()) > 16000:
        raise ValueError("Pilot input exceeds 16KB limit")
    body = json.dumps(
        {
            "model": MODEL,
            "input": prompt,
            "store": False,
            "service_tier": "default",
            "reasoning": {"effort": "low"},
            "max_output_tokens": 2048,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "robot_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"decision": {"type": "string", "enum": list(CRITERIA)}},
                        "required": ["decision"],
                        "additionalProperties": False,
                    },
                }
            },
        }
    ).encode()
    key = Path(os.environ["ASTRA_KEY_FILE"]).read_text(encoding="utf-8-sig").strip()
    if not key.startswith(("sk-proj-", "sk-svcacct-")) or any(c.isspace() for c in key):
        raise ValueError("Expected an OpenAI project credential file")
    ledger = Path(os.environ.get("ASTRA_BUDGET_LEDGER", str(Path.home() / ".local/share/rtbench/astra-budget.sqlite")))
    call_id = reserve(ledger)
    request = urllib.request.Request(
        ENDPOINT, data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    )
    start = time.monotonic_ns()
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("oversized response")
        result = json.loads(raw)
        usage = result["usage"]
        if result.get("status") != "completed":
            raise ValueError("incomplete response")
        texts = [
            part["text"]
            for item in result["output"]
            if item.get("type") == "message"
            for part in item["content"]
            if part.get("type") == "output_text"
        ]
        decision = json.loads("".join(texts))
        if set(decision) != {"decision"} or decision["decision"] not in CRITERIA:
            raise ValueError("invalid decision")
        if not str(result.get("model", "")).startswith(MODEL):
            raise ValueError("unexpected response model")
        inp, out = usage["input_tokens"], usage["output_tokens"]
        if type(inp) is not int or type(out) is not int or not (0 <= inp <= 18000 and 0 <= out <= 2048):
            raise ValueError("usage out of bounds")
        cache_write = usage.get("input_tokens_details", {}).get("cache_write_tokens", 0)
        if type(cache_write) is not int or not 0 <= cache_write <= inp:
            raise ValueError("invalid cache usage")
        cost = inp * 10 / 1e6 + cache_write * 2.5 / 1e6 + out * 50 / 1e6  # ignore cached-read discount
        detail = {
            "model": result["model"],
            "decision": decision["decision"],
            "usage": usage,
            "latency_ms": (time.monotonic_ns() - start) / 1e6,
            "estimated_cost_usd": cost,
            "kind": "provider call, not a simulation result",
        }
        with sqlite3.connect(ledger, timeout=30) as db:
            db.execute(
                "UPDATE calls SET charge=?,status=?,detail=? WHERE id=?",
                (cost, "completed", json.dumps(detail), call_id),
            )
        return detail
    except Exception as exc:
        status = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        raise RuntimeError("Astra request failed: " + status + "; reservation retained") from None


def decide(state):
    return {"decision": evaluate(state)["decision"]}


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                evaluate(
                    {
                        "environment": "YAM simulation connectivity test only",
                        "observation": "Target moved to a new reachable location; scene is clear and safe.",
                        "current_plan": "Reach the previous target location.",
                    }
                ),
                indent=2,
            )
        )
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1)
