"""Episode-level reports. Small pilots are descriptive, not speedup claims."""

import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    a = p.parse_args()
    rows = json.loads((a.run / "summary.json").read_text())
    diagnostic = all(r["diagnostic"] for r in rows)
    title = "Offline execution check — identical local workers" if diagnostic else "Continuous A/B simulation pilot"
    lines = [
        f"# {title}",
        "",
        "Each row below summarizes whole episodes; percentiles within an episode are not independent trials.",
        "",
        "| System | Attempts (episodes) | Pickup success | Median workflow (ms) | Median change → fresh dispatch (ms) | Stale proposals | RTF range |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for index, system in enumerate(["A", "B"]):
        group = [r for r in rows if r["system"] == system]
        latency = [r["workflow_ms"]["p50"] for r in group if r["workflow_ms"]["p50"] is not None]
        response = [r["change_to_fresh_dispatch_ms"] for r in group if r["change_to_fresh_dispatch_ms"] is not None]
        median = lambda x: f"{np.median(x):.1f}" if x else "not observed"
        rtf = [r["real_time_factor"] for r in group]
        lines.append(
            f"| {system} | {len(group)} | {sum(r['success'] for r in group)}/{len(group)} | {median(latency)} | {median(response)} | {sum(r['gate_rejections'].get('stale_scene', 0) for r in group)} | {min(rtf):.3f}–{max(rtf):.3f} |"
        )
        for ax, values in zip(axes, [latency, response]):
            ax.scatter([index] * len(values), values, s=40)
    for ax, title in zip(axes, ["Episode median workflow latency", "Change to fresh controller dispatch"]):
        ax.set_xticks([0, 1], ["A", "B"])
        ax.set_title(title)
        ax.set_ylabel("Milliseconds")
        ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(a.run / "latency.png", dpi=160)
    plt.close(fig)
    lines += [
        "",
        "No uncertainty claim is made from this small development sample. Missing responses and unsuccessful episodes remain in the JSON summaries.",
        "",
        "The scene change is a scripted motion reversal. Camera mode estimates position from RGB-D but does not yet detect scene changes from images. These runs use a known red cube and experimental simulation finger contacts.",
        "",
        "Native eligible-to-start timing uses output-ready timestamps from wrappers; native internal queue/dispatch timestamps are unavailable. Rust separately records dispatch, worker and result receipt. Neither number is pure scheduler overhead.",
        "",
        "Decision-worker latency includes provider request construction, networking and parsing (or the diagnostic sleep). Normal GaP tracing remains enabled. WSL results are development measurements, not native-Linux publication measurements.",
    ]
    (a.run / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
