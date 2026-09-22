"""Freeze labeled states, then evaluate both providers on identical inputs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import time

from executors import DECISIONS
from settings import validate_credentials


def load_examples(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = set()
    for row in rows:
        if (
            set(row) != {"id", "episode_id", "state", "gold_decision", "provenance"}
            or row["gold_decision"] not in DECISIONS
            or not isinstance(row["state"], dict)
            or not all(isinstance(row[k], str) and row[k] for k in ["id", "episode_id", "provenance"])
            or row["id"] in ids
        ):
            raise ValueError("Expected unique IDs, episode groups, provenance, state and a valid gold decision")
        ids.add(row["id"])
    if not rows:
        raise ValueError("Empty dataset")
    return rows


def score(records):
    report = {}
    paired = {}
    for system in ["A", "B"]:
        rows = [r for r in records if r["system"] == system]
        valid = [r for r in rows if r.get("decision") in DECISIONS]
        correct = sum(r["decision"] == r["gold_decision"] for r in valid)
        report[system] = {
            "n": len(rows),
            "correct": correct,
            "invalid_or_failed": len(rows) - len(valid),
            "accuracy": correct / len(rows) if rows else None,
            "confusion_matrix": dict(Counter(r["gold_decision"] + " -> " + r.get("decision", "invalid") for r in rows)),
            "estimated_cost_usd": sum(r.get("estimated_cost_usd", 0) for r in rows),
        }
        for row in rows:
            paired.setdefault(row["id"], {})[system] = row.get("decision") == row["gold_decision"]
    complete = [v for v in paired.values() if set(v) == {"A", "B"}]
    report["paired"] = {
        "n": len(complete),
        "A_only_correct": sum(r["A"] and not r["B"] for r in complete),
        "B_only_correct": sum(r["B"] and not r["A"] for r in complete),
    }
    report["quality_gate"] = (
        "not evaluated: requires a preregistered sample size and episode-clustered non-inferiority analysis"
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("examples", type=Path)
    freeze.add_argument("output", type=Path)
    run = sub.add_parser("run")
    run.add_argument("dataset", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("--live", action="store_true", required=True)
    run.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    from astra_provider import MODEL as ASTRA
    from jev_provider import MODEL as JEV, INSTRUCTIONS, CRITERIA

    contract = {
        "models": {"A": ASTRA, "B": JEV},
        "instructions": INSTRUCTIONS,
        "criteria": CRITERIA,
        "adapter_sha256": {
            f: hashlib.sha256((Path(__file__).parent / f).read_bytes()).hexdigest()
            for f in ["astra_provider.py", "jev_provider.py"]
        },
    }
    if a.command == "freeze":
        rows = load_examples(a.examples)
        a.output.mkdir(parents=True, exist_ok=False)
        data = "".join(json.dumps(r, sort_keys=True, allow_nan=False) + "\n" for r in rows).encode()
        (a.output / "examples.jsonl").write_bytes(data)
        (a.output / "manifest.json").write_text(
            json.dumps(
                dict(
                    contract,
                    sha256=hashlib.sha256(data).hexdigest(),
                    n=len(rows),
                    episodes=len({r["episode_id"] for r in rows}),
                ),
                indent=2,
            )
        )
        return
    validate_credentials()
    manifest = json.loads((a.dataset / "manifest.json").read_text())
    data = a.dataset / "examples.jsonl"
    if manifest["sha256"] != hashlib.sha256(data.read_bytes()).hexdigest() or any(
        manifest[k] != v for k, v in contract.items()
    ):
        raise ValueError("Frozen dataset or provider contract changed")
    rows = load_examples(data)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / "manifest.json").write_text(json.dumps(dict(manifest, collection_seed=a.seed), indent=2))
    from astra_provider import evaluate as astra
    from jev_provider import evaluate as jev

    rng = random.Random(a.seed)
    rng.shuffle(rows)
    records = []
    for row in rows:
        systems = ["A", "B"]
        rng.shuffle(systems)
        for system in systems:
            result = {k: row[k] for k in ["id", "episode_id", "gold_decision"]}
            result["system"] = system
            started = time.monotonic_ns()
            try:
                result.update(({"A": astra, "B": jev}[system])(row["state"]))
            except Exception as exc:
                result["error_type"] = type(exc).__name__
            result["elapsed_ms"] = (time.monotonic_ns() - started) / 1e6
            records.append(result)
            with (a.output / "decisions.jsonl").open("a") as stream:
                stream.write(json.dumps(result) + "\n")
            (a.output / "summary.json").write_text(json.dumps(score(records), indent=2))


if __name__ == "__main__":
    main()
