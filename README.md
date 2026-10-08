# JevGaP

JevGaP is an open-source testbed for studying how AI coding agents build and
improve robot-control policies with **GaP, CaP-X, ASPIRE and ENPIRE**. It provides
a shared 13-task protocol, configurable harness adapters and independent task
scoring for simulation and SE3 station evaluation.

A harness provides the tools and execution workflow around a policy. The
experiments examine task success, recovery, latency and improvement under
declared model, compute and robot-trial budgets.

## Supported harnesses

| Harness | Config selector | Evaluation entry point |
|---|---|---|
| [GaP](https://github.com/graph-robots/graph-as-policy) | `native-gap` | Typed policy graphs executed by the native GaP runtime |
| [CaP-X](https://github.com/capgym/cap-x) | `cap` | Python policy generation and execution through the upstream headless launcher |
| [ASPIRE](https://github.com/NVlabs/ASPIRE) | `aspire` | Saved policies executed through the upstream script runner |
| [ENPIRE](https://github.com/NVlabs/ENPIRE) | `enpire` | Supplied policies and environments evaluated through the upstream TrialRunner |

The [testing plan](task_suite/TESTING_PLAN.md) covers all four harnesses across
all 13 tasks: **52 harness/task combinations**, expanded by layouts, seeds and
repetitions. Each batch runs one selected harness. The study tracks completed,
failed and blocked combinations and keeps native, local and operator outcomes
separate.

## Get started

Install the Python 3.12 coordinator and pinned dependencies using
[SETUP.md](task_suite/SETUP.md). Then, from the repository root with that
environment activated:

```bash
python scripts/task_suite.py init --directory local-config/harnesses --gap-root vendor/graph-as-policy
python scripts/task_suite.py harnesses
python scripts/task_suite.py plan --config local-config/harnesses/enpire.local.json
```

`init` creates private configuration templates. `plan` lists the selected trials
and missing setup without launching a model or robot. Select the corresponding
experiment file for each harness:

| Harness | Configuration under `local-config/harnesses/` |
|---|---|
| GaP | `replay.json` for offline diagnostics; `se3.local.json` for SE3 |
| CaP-X | `cap.local.json` |
| ASPIRE | `aspire.local.json` |
| ENPIRE | `enpire.local.json` |

For a known-answer software check without model requests or station access:

```bash
python scripts/task_suite.py batch --config local-config/harnesses/replay.json --output results/tasks/replay-001
```

Use an unused output directory for every run. Replay tests software contracts;
its scores do not measure model quality or robot performance. Follow
[HARNESSES.md](task_suite/HARNESSES.md) to install an upstream environment, bind
its native task implementation and run configuration checks. Agents must ask
before spending OpenAI API credits; a configured key or `--live` flag does not
replace user approval.

## Implementation and deployment requirements

The repository includes task contracts, scenario templates, local scoring,
batch execution, GaP replay fixtures, an SE3 Python Policy bridge and adapters
for all four harnesses. Offline tests exercise configuration, execution,
failure handling and score boundaries.

Physical trials need station access, calibrated perception and control,
independent measurements and task/environment implementations for each harness.
Complete policy-development workflows and matched resource enforcement also
require integration and validation. The evaluation adapters alone do not run
every upstream search, repair or training workflow. See the
[task suite](task_suite/README.md), [driver contract](task_suite/DRIVER.md) and
[testing plan](task_suite/TESTING_PLAN.md) for requirements and study design.

## Documentation and experiments

| Guide | What it covers |
|---|---|
| [Harness setup](task_suite/HARNESSES.md) | Select GaP, CaP-X, ASPIRE or ENPIRE; configure native workflows and evaluator exports |
| [Testing plan](task_suite/TESTING_PLAN.md) | Shared tasks, commissioning, controlled comparisons and coverage criteria |
| [Architecture](docs/architecture.md) | Harness dispatch, scoring boundaries and graph executor semantics |
| [Configuration](docs/configuration.md) | Experiment files, model settings and budget scopes |
| [Executor and inference experiment](docs/executor-experiment.md) | Compare native GaP + Astra with a Rust executor + Jev on matched simulated tasks |
| [Continuous decisions](docs/continuous.md) | Test repeated decisions, stale-response rejection and perception latency |
| [Station integration](docs/station.md) | Observation, admission and completion contracts using fake and MuJoCo stations |
| [Measured results](docs/results.md) | Simulation measurements, sample counts, provenance and limitations |

## Project layout

```text
task_suite/           Four-harness task contracts, adapters, configuration and scoring
scripts/              Experiment runners, providers, diagnostics and analysis
crates/runtime/       Rust required-input scheduler and Unix-socket transport
workflows/yam_pickup/  Proposal-only GaP workflow for executor experiments
tests/                Gate, importer, contact and budget checks
docs/                 Methods, setup guides and selected evidence
third_party/          Upstream license notices
```

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and offline validation,
and [SECURITY.md](SECURITY.md) for credentials and deployment boundaries.
Project code is licensed under [Apache-2.0](LICENSE). Dependencies retain their
own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). This project is
independent of the upstream projects and model providers.
