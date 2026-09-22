from collections import Counter
import json
import statistics
from .contracts import LOCAL_CLOCK


def distribution(values):
    values = sorted(values)
    return dict(
        n=len(values),
        p50=statistics.median(values) if values else None,
        p95=values[min(len(values) - 1, int(0.95 * len(values)))] if values else None,
    )


def write_report(output, summary, events, workflows):
    summary["rejections"] = dict(
        Counter(
            e["reason"]
            for e in events
            if e["kind"] in {"admission", "proposal_rejected", "observation_rejected"} and e.get("reason")
        )
    )
    summary["execution_rejections"] = dict(
        Counter(e.get("reason") for e in events if e["kind"] == "execution" and e["status"] == "rejected")
    )
    summary["workflow_ms"] = distribution([(w["returned_ns"] - w["submitted_ns"]) / 1e6 for w in workflows])
    summary["perception_ms"] = distribution(
        [(e["end_ns"] - e["start_ns"]) / 1e6 for e in events if e["kind"] == "perception"]
    )
    dispatches = {e["command_id"]: e["at_ns"] for e in events if e["kind"] == "dispatch"}
    proposals = {e["command_id"]: e for e in events if e["kind"] == "proposal"}
    summary["observation_to_dispatch_ms"] = distribution(
        [
            (at - proposals[key]["captured_ns"]) / 1e6
            for key, at in dispatches.items()
            if key in proposals and proposals[key]["source_clock"] == LOCAL_CLOCK
        ]
    )
    summary["acknowledgement_ms"] = distribution(
        [(e["at_ns"] - dispatches[e["command_id"]]) / 1e6 for e in events if e["kind"] == "acknowledgement"]
    )
    for name, rows in [("events", events), ("workflows", workflows)]:
        (output / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    text = f"""# Station integration check

Mode: **{summary["mode"]}**. Station measurements are in summary.json.
Executor: {summary["executor"]}. Provider: {summary["provider"]}.

- Workflow attempts: {summary["calls"]}; failures: {summary["workflow_failures"]}.
- Replaced pending observations: {summary["observation_replacements"]}.
- Unresolved commands: {len(summary["unresolved_commands"])}.
- Execution outcomes: {dict(Counter(summary["statuses"].values()))}.
- Admission/observation rejections: {summary["rejections"]}.
- Workflow latency in ms: {summary["workflow_ms"]}.

Acceptance is not completion. A shadow proposal is not an executed command.
Diagnostic workers make no model calls. This is an integration check, not a
performance comparison or evidence of physical hardware readiness. Ground-truth
and experimental RGB-D sources are configured separately. Task success is reported
from the station's independent measurements, not inferred from model decisions.
"""
    (output / "report.md").write_text(text)
