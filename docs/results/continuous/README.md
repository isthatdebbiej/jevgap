# Continuous-loop development results

These are development runs on WSL, separate from the original one-authorization
pickup demo. Run configurations and individual episode summaries are retained
alongside this page. All attempts are included.

| Run | Episodes A / B | Pickup successes A / B | Purpose |
|---|---:|---:|---|
| Identical 400 ms local workers | 3 / 3 | 3 / 1 | Execution and stale-response checks |
| Initial synchronous camera | 1 / 1 | 0 / 0 | Failed: view occlusion and rendering stalls |
| Asynchronous camera | 1 / 1 | 0 / 0 | Camera integration; physics near 1x, perception still unreliable |
| Live Astra / Jev | 1 / 1 | 1 / 1 | Continuous model-call integration |

The live pair used simulator ground-truth positions. Its measured times were:

| Metric | A: native GaP + Astra | B: GaP + Jev + custom Rust executor |
|---|---:|---:|
| Confirmed pickup | 11.87 s | 5.73 s |
| Motion-change to fresh controller dispatch | 5.70 s | 0.47 s |
| Median full workflow latency | 2,446 ms | 331 ms |
| Completed model calls | 4 | 11 |
| Rejected stale-scene proposals | 1 | 0 |
| Proposals returned after episode end | 1 | 0 |

This is one matched live pair, not a statistically established speedup. Both the
model and execution substrate differ. A scripted motion reversal at one second
invalidated the prior scene; it was not detected by a vision model. Both models
receive synthetic structured state and share the same tracker and gate.

The asynchronous RGB-D detector found the cube in 19/59 A frames and 17/54 B
frames. Median position error on detected frames was about 19 mm; missing frames
are not included in that error statistic. Neither camera episode picked up the
cube. These are failed perception trials, not hardware-ready results.

The code changed across the camera iterations. Each configuration preserves the
source hashes at collection time; later formatting, summary-field additions and
a reset of the consecutive-contact counter during pauses postdate these runs.
The earlier runs have not been silently relabeled as measurements of that final
revision. The latest code passes offline tests; these small pilots guide further
work rather than serving as a frozen publication benchmark.

See [reproduction and limitations](../../continuous.md),
[the live report](continuous-live-v1/report.md) and
[the camera report](continuous-camera-v2/report.md).

[Watch the live continuous-loop pair](../../assets/continuous-moving-cube.mp4). Playback is synchronized at 1x with elapsed-time overlays.
