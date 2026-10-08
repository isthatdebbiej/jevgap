# Continuous-decision experiment results

These WSL runs compare repeated decisions from native GaP + Astra and the
Rust executor + Jev while a shared controller tracks a moving cube. Configurations
and individual episode summaries are retained alongside this page, including
failed attempts. Use the [four-harness testing plan](../../../task_suite/TESTING_PLAN.md)
for the 13-task evaluation protocol.

| Run | Episodes A / B | Pickup successes A / B | Purpose |
|---|---:|---:|---|
| Identical 400 ms local workers | 3 / 3 | 3 / 1 | Execution and stale-response checks |
| Synchronous camera | 1 / 1 | 0 / 0 | Failed: view occlusion and rendering stalls |
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

Each run configuration records the source hashes used to collect its
measurements. Reproduce runs with those revisions: camera processing, summary
fields and paused-contact counter handling vary by revision. The reported
measurements apply to their recorded code and configuration. These small pilots
provide integration evidence, not a statistically established performance ranking.

See [reproduction and limitations](../../continuous.md),
[the live report](continuous-live-v1/report.md) and
[the camera report](continuous-camera-v2/report.md).

[Watch the live continuous-loop pair](../../assets/continuous-moving-cube.mp4). Playback is synchronized at 1x with elapsed-time overlays.
