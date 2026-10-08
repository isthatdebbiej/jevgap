# Executor and inference results

These measurements compare native GaP + Astra with the Rust executor + Jev
on simulated moving-cube and joint-target tasks. The [experiment guide](executor-experiment.md)
describes the runners and controller. Report results for the 13-task harness
study using its [testing plan](../task_suite/TESTING_PLAN.md), coverage matrix
and matched evaluation protocol.

## Moving cube: one matched pair

| System | First lift threshold | Confirmed pickup | Retained at 18 s |
|---|---:|---:|---|
| A — Native GaP + Astra | 6.62 s | 8.79 s | Yes |
| B — GaP + Jev + custom Rust executor | 3.67 s | 5.42 s | Yes |

Confirmed pickup requires cube-center height >5 cm above the table and opposing
finger contacts for 300 consecutive 1 ms physics steps. First crossing alone is
not sufficient. Each system made one live decision request, then used the same
ground-truth tracking controller. Physics ran at approximately 1× wall time.

The cube moved about 21.1 mm before A closed and 2.5 mm before B closed. The
different positions result from different decision delays against the same initial
state and moving-cube dynamics. The video stops two seconds after the slower
confirmed pickup; the included trajectories cover the full episodes.

**N=1 per system.** No confidence interval, generalized speedup or isolated runtime
benefit is claimed. The controller uses approximate finger pads, an elliptic
friction solver and simulator ground truth. This is not a validated YAM digital
twin or a grasp-policy benchmark.

[Video](assets/moving-cube.mp4) · [Metrics](results/moving-cube/metrics.json) ·
[A logs](results/moving-cube/A/) · [B logs](results/moving-cube/B/)

## Joint target: five matched pairs

| Metric | A | B |
|---|---:|---:|
| Task success | 5/5 | 5/5 |
| Median of episode-median workflow latency | 1,740 ms | 305 ms |
| Median change → fresh command, four changes each | 3,975 ms | 520 ms |
| Estimated API cost | $0.13091 | $0.00392 |

One static pair, two early-change pairs and two late-change pairs. This was a
different, simpler joint-target task; do not pool it with moving-cube pickup.
Five successes imply a broad Wilson 95% success interval of about 57–100% per
system. Both pipelines used normal model calls and native GaP tracing. Rejected
and episode-ended proposals remain in the logs.

[Metrics](results/joint-target/headline.json) · [Configuration](results/joint-target/config.json)

## Provenance and limits

Collected under WSL2 using the pinned GaP/I2RT revisions and Python/MuJoCo
dependencies in this repository. Source was on mounted Windows storage, while
environments, Rust outputs, sockets and unmodified logs were on Linux storage.
Use native Linux and Linux-hosted source for a publication-quality timing study.

Public evidence uses A/B labels consistently. Unmodified local logs are retained;
public copies normalize system labels and tool namespaces. Measured numbers
and task outcomes are preserved. Local paths, host identifiers,
billing ledgers and private source manifests are omitted. Credential files were
never part of result records. Finger-contact and controller development runs were
separate from the delivered live episodes.

Rendered footage reconstructs recorded physics states at synchronized 1× wall
time; rendering does not perturb measured episode timing. Models and task inputs
are documented in the configs. No hardware or semantic non-inferiority result
has been collected.
