"""Generate an honest, episode-level report from YAM A/B pilot logs."""

import argparse
import json
from pathlib import Path
import numpy as np


def median(values):
    return float(np.median(values)) if values else None


def fmt(v):
    return "not observed" if v is None else f"{v:,.0f}"


def bootstrap(values):
    if len(values) < 5:
        return None
    rng = np.random.default_rng(20260920)
    data = np.array(values)
    med = np.median(rng.choice(data, (5000, len(data))), axis=1)
    return [float(x) for x in np.percentile(med, [2.5, 97.5])]


def wilson(k, n):
    if not n:
        return None
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [100 * (center - half), 100 * (center + half)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    args = p.parse_args()
    rows = json.loads((args.run / "summary.json").read_text())
    cfg = json.loads((args.run / "config.json").read_text())
    if cfg["diagnostic"]:
        raise ValueError("Do not publish diagnostic providers as A/B")
    lines = [
        "# YAM A/B simulation integration pilot",
        "",
        "**Measured simulation results. No physical hardware trials.**",
        "",
        "A = native GaP + OpenAI GPT-6 Astra (low reasoning). B = the same GaP workflow compiled to the Rust executor + TypeSafe Jev 1.13.0.",
        "This measures the combined execution/inference path on a deliberately simple joint-target task. It does not isolate Rust speedup or establish semantic decision non-inferiority.",
        "",
        "| Condition | System | Success / attempted (95% Wilson CI) | Workflow ms¹ | Fresh response / changes | Change → fresh dispatch ms² | Real-time factor |",
        "|---|---|---|---|---|---|---|",
    ]
    aggregates = []
    for condition in ["static", "early", "late"]:
        for system in ["A", "B"]:
            subset = [r for r in rows if r["condition"] == condition and r["system"] == system]
            vals = [median(r["workflow_ms"]) for r in subset if r["workflow_ms"]]
            fresh = [r["change_to_fresh_dispatch_ms"] for r in subset if r["change_to_fresh_dispatch_ms"] is not None]
            k = sum(r["success"] for r in subset)
            n = len(subset)
            ci = wilson(k, n)
            entry = {
                "condition": condition,
                "system": system,
                "attempted": n,
                "success": k,
                "success_ci95": ci,
                "median_episode_workflow_ms": median(vals),
                "workflow_median_ci95": bootstrap(vals),
                "fresh_responses": len(fresh),
                "changed_trials": 0 if condition == "static" else n,
                "median_fresh_response_ms": median(fresh),
                "fresh_response_ci95": bootstrap(fresh),
                "median_real_time_factor": median([r["real_time_factor"] for r in subset]),
            }
            aggregates.append(entry)
            success = f"{k}/{n} ({ci[0]:.0f}–{ci[1]:.0f}%)" if ci else "not evaluated"
            lines.append(
                f"| {condition} | {system} | {success} | {fmt(median(vals))} | {len(fresh)}/{entry['changed_trials']} | {fmt(median(fresh))} | {entry['median_real_time_factor']:.3f} |"
            )
    lines += [
        "",
        "¹ Median across per-episode median workflow latencies, including proposal computations later rejected by the gate. Warmup calls are not silently removed. All calls within each episode are retained.",
        "² Observed responses only. Missing fresh responses are failures to respond by episode end, not zero latency; counts above expose this censoring. Static trials have no change event.",
        "",
        "## Paired comparisons",
        "",
        "Differences below are B minus A, matched by seed and condition. Negative latency differences favor B. Confidence intervals are withheld when there are fewer than five pairs; this pilot is too small for reliable condition-specific latency inference.",
        "",
    ]
    comparisons = []
    for c in ["static", "early", "late"]:
        pairs = []
        for a in [r for r in rows if r["system"] == "A" and r["condition"] == c]:
            b = next((r for r in rows if r["system"] == "B" and r["condition"] == c and r["seed"] == a["seed"]), None)
            if b and a["workflow_ms"] and b["workflow_ms"]:
                pairs.append(median(b["workflow_ms"]) - median(a["workflow_ms"]))
        ci = bootstrap(pairs)
        comparisons.append(
            {"condition": c, "paired_n": len(pairs), "median_workflow_difference_ms": median(pairs), "ci95": ci}
        )
        lines.append(
            f"- {c}: N={len(pairs)}, median paired workflow difference {fmt(median(pairs))} ms; 95% bootstrap CI "
            + (f"[{ci[0]:.0f}, {ci[1]:.0f}] ms." if ci else "not estimated.")
        )
    lines += [
        "",
        "## Admission and completion accounting",
        "",
        "| System | Workflow calls | Gate rejections | Deadline misses (>5s) | Median no-current-plan fraction |",
        "|---|---|---|---|---|",
    ]
    for s in ["A", "B"]:
        ss = [r for r in rows if r["system"] == s]
        lines.append(
            f"| {s} | {sum(r['workflow_samples'] for r in ss)} | {sum(sum(r['rejections'].values()) for r in ss)} | {sum(r['deadline_misses'] for r in ss)} | {100 * median([r.get('no_current_target_fraction', 0) for r in ss]):.1f}% |"
        )
    lines += [
        "",
        "No-current-plan fraction counts control ticks without an admitted plan for the current scene; the previous movement may still continue. In-flight calls finishing after the 12-second episode are logged and rejected as episode-ended. Missing or failed responses are retained in each episode summary.",
        "",
        "## Scope and limitations",
        "",
        "- Ground-truth structured joint observations at 20 Hz; no camera perception or grasping. Target changes are injected and detected simultaneously, so detector latency is excluded.",
        "- Physics advances independently during inference, with 1ms integration and 10ms pacing. Reported real-time factor is simulation time / wall time.",
        "- Common controller: position error gains [80,80,80,10,10,10], gravity/bias compensation, ±10 Nm applied-force clipping, implicit damping [5,5,5,1.5,1.5,1.5]. This is an experimental controller, not validated YAM actuator dynamics.",
        "- Official arm and linear-4310 gripper meshes/inertia are reused. Adjacent base/link1 mesh contact is excluded because the visual geometry overlaps at the bearing. Other contacts remain enabled.",
        "- Both executors have eight maximum workers; native GaP uses its original in-process execution and tracing; Rust uses persistent Python processes over Unix sockets. This linear workflow offers no parallel scheduling advantage.",
        "- One observation in flight per system. Both use a 5-second age budget, bounded one-proposal gate, and dispatch-time freshness recheck. Decision requests have a 200ms pause between completions, not a fixed arrival-rate benchmark.",
        "- Success requires all six joints within 0.04 rad of the current target for at least the final 250ms. This checks target tracking, not semantic reasoning quality.",
        "- This task could use deterministic rules. Model substitution here demonstrates integration and responsiveness, not the need for an LLM or superiority on expensive semantic reasoning.",
        "- WSL2 exploratory results; not native-Linux publication measurements. Source is on mounted Windows storage; environments, sockets, build outputs and original result logs are on Linux storage.",
        "- API costs are separate ledger estimates; no hardware claims, safety certification, or generalized performance claims.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "cd jevgap",
        "CARGO_TARGET_DIR=$HOME/.cache/rtbench/target ~/.cargo/bin/cargo build --release --locked",
        "~/.local/share/rtbench/yam-venv/bin/python scripts/yam_sim.py --live --pairs 5 --duration 12 --output $HOME/.local/share/rtbench/results/yam-ab2-new",
        "```",
        "",
        "Requires the two local credential files; do not distribute them. Full config, JSONL timing/gate/trajectory logs and per-episode summaries accompany the report. Videos render recorded physics trajectories at synchronized 1× wall-time playback; they are not physical-robot footage.",
    ]
    (args.run / "REPORT.md").write_text("\n".join(lines) + "\n")
    (args.run / "aggregates.json").write_text(json.dumps({"cells": aggregates, "paired": comparisons}, indent=2))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for system, color, offset in [("A", "#7963b6", -0.12), ("B", "#188d89", 0.12)]:
        for i, c in enumerate(["static", "early", "late"]):
            subset = [r for r in rows if r["system"] == system and r["condition"] == c]
            vals = [median(r["workflow_ms"]) for r in subset if r["workflow_ms"]]
            axes[0].scatter([i + offset] * len(vals), vals, color=color, alpha=0.75, label=system if i == 0 else None)
            fresh = [r["change_to_fresh_dispatch_ms"] for r in subset if r["change_to_fresh_dispatch_ms"] is not None]
            axes[1].scatter([i + offset] * len(fresh), fresh, color=color, alpha=0.75)
    for ax, title in zip(
        axes, ["Workflow latency: each dot is an episode median", "Change → fresh dispatch: observed responses"]
    ):
        ax.set_xticks(range(3), ["static", "early", "late"])
        ax.set_ylabel("milliseconds")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.2)
    axes[0].legend()
    fig.suptitle("YAM free-space simulation pilot · A: GaP + Astra · B: GaP/Rust + Jev", fontsize=11)
    fig.tight_layout()
    fig.savefig(args.run / "metrics.png", dpi=180)
    fig.savefig(args.run / "metrics.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
