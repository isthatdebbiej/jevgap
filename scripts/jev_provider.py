"""Pinned TypeSafe adapter. No retries; durable reservations cover uncertain calls."""

import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
RATE = 0.042 / 1_000_000
# Above the documented 64k input context cost ($0.002688).
RESERVATION = 0.003
CAP = 5.0
CRITERIA = {
    "continue": "The current plan remains appropriate for the observed task state.",
    "reperceive": "Observation is missing, ambiguous, or occluded; obtain a fresh observation before planning.",
    "replan": "The task is feasible but the target or relevant scene changed and the current plan needs updating.",
    "abort": "The task is unsafe or infeasible under the stated constraints.",
}
INSTRUCTIONS = (
    "Choose the next high-level decision for the simulated robot using only the supplied state. "
    "Prioritize safety, then sufficient observation, then plan validity. Do not invent observations."
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def reserve(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as db:
        db.execute("CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, charge REAL, status TEXT, detail TEXT)")
        db.execute("BEGIN IMMEDIATE")
        spent = db.execute("SELECT COALESCE(SUM(charge),0) FROM calls").fetchone()[0]
        if spent + RESERVATION > CAP:
            raise RuntimeError("Jev $5 experiment budget exhausted")
        cursor = db.execute("INSERT INTO calls(charge,status) VALUES (?,?)", (RESERVATION, "reserved"))
        return cursor.lastrowid


def evaluate(state):
    body = json.dumps(
        {
            "model": MODEL,
            "state": state,
            "questions": {"decision": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}},
        },
        allow_nan=False,
    ).encode()
    if len(body) > 16000:
        raise ValueError("Pilot request exceeds 16KB limit")
    key_path = Path(os.environ["JEV_KEY_FILE"])
    key = key_path.read_text(encoding="utf-8-sig").strip()
    if not key or any(c.isspace() for c in key):
        raise ValueError("Expected a file containing only the Jev key")
    ledger = Path(os.environ.get("JEV_BUDGET_LEDGER", str(Path.home() / ".local/share/rtbench/jev-budget.sqlite")))
    call_id = reserve(ledger)
    request = urllib.request.Request(
        ENDPOINT, data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    )
    start = time.monotonic_ns()
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("oversized response")
        result = json.loads(raw)
        answer = result["answers"]["decision"]
        tokens = result["usage"]["input_tokens"]
        if (
            result["model"] != MODEL
            or answer["type"] != "choice"
            or answer["choice"] not in CRITERIA
            or type(tokens) is not int
            or not 0 <= tokens <= 64000
        ):
            raise ValueError("provider contract mismatch")
        detail = {
            "model": result["model"],
            "decision": answer["choice"],
            "usage": result["usage"],
            "latency_ms": (time.monotonic_ns() - start) / 1e6,
            "estimated_cost_usd": tokens * RATE,
            "kind": "provider call, not a simulation result",
        }
        with sqlite3.connect(ledger, timeout=30) as db:
            db.execute(
                "UPDATE calls SET charge=?,status=?,detail=? WHERE id=?",
                (tokens * RATE, "completed", json.dumps(detail), call_id),
            )
        return detail
    except Exception as exc:
        # Never expose remote error bodies, request headers, or credential values.
        status = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        raise RuntimeError("Jev request failed: " + status + "; reservation retained") from None


def decide(state):
    return {"decision": evaluate(state)["decision"]}


if __name__ == "__main__":
    try:
        result = evaluate(
            {
                "environment": "YAM simulation connectivity test only",
                "observation": "Target moved to a new reachable location; scene is clear and safe.",
                "current_plan": "Reach the previous target location.",
            }
        )
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1)
