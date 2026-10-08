# Configuration

## Four-harness task suite

The current study selects GaP, CaP-X, ASPIRE or ENPIRE through an experiment
configuration. Generate the private templates with the coordinator's `init`
command, then choose the matching file for each batch:

| Harness | Generated experiment | Mode | Harness-specific settings |
|---|---|---|---|
| GaP | `replay.json` or `se3.local.json` | `replay` or `se3` | GaP checkout; for SE3, station/driver and Responses model configuration |
| CaP-X | `cap.local.json` | `upstream` | Upstream profile plus native task YAML bindings |
| ASPIRE | `aspire.local.json` | `upstream` | Upstream profile plus saved programs and native Hydra task configuration |
| ENPIRE | `enpire.local.json` | `upstream` | Upstream profile plus environment/policy factories and their configuration |

Use the same task inventory, prescribed layouts, seeds and repetitions across
the four configurations. A batch runs one selected harness; the study matrix
tracks all four. `plan` shows selected trials and `doctor` reports configuration
blockers without launching native runners. Start with [harness setup](../task_suite/HARNESSES.md)
for the commands, profile fields and independent evidence contract.

[Coordinator installation](../task_suite/SETUP.md) also documents the native GaP
station/model configuration. Its Responses budget ledger applies to native GaP;
upstream workflows use their own model settings and spending controls. Match and
record those controls as required by the [testing plan](../task_suite/TESTING_PLAN.md).

## Historical Astra/Jev A/B defaults

The settings below belong to the earlier moving-cube and executor experiments.

| Setting | Current default |
|---|---|
| Python | 3.12.3 |
| Rust | 1.98.1 |
| A model | OpenAI `gpt-6-astra`, low reasoning, 2,048 output-token maximum |
| B model | TypeSafe `jev-1.13.0` |
| A endpoint | `https://api.openai.com/v1/responses` |
| B endpoint | `https://api.typesafe.ai/v1/systemone` |
| Credential variables | `ASTRA_KEY_FILE`, `JEV_KEY_FILE` |
| Default environment | `$HOME/.local/share/rtbench/yam-venv` |
| Default build output | `$HOME/.cache/rtbench/target` |
| Default ledgers | `$HOME/.local/share/rtbench/{astra,jev}-budget.sqlite` |

`.env.example` documents variable names; scripts do not automatically load `.env`.
Export variables explicitly. Never place real keys in a config or source file.
The preflight reads only whether the provided files exist and are nonempty.

The legacy providers' Python constants define their model, endpoint, timeout and
spending policy. `ASTRA_BUDGET_LEDGER` and `JEV_BUDGET_LEDGER` can relocate ledgers.
Keep each ledger shared by all pilot workers, and retain it between runs. Removing
or changing it resets local accounting. Default caps are $100 and $5, respectively;
change constants deliberately if running a separately budgeted experiment.

Reservations are atomic across processes. Successful calls settle against token
usage; failures retain their reservation because billing may be uncertain. There
are no automatic retries. These caps do not include calls made by unrelated
software, taxes or future price changes. Pricing assumptions are in the adapters
and should be verified before a new study.

New output directories are mandatory. Raw source/host manifests are useful locally
but can contain machine paths or identifiers; do not publish them unchecked.
`results/`, `vendor/`, local archives, caches and credentials are ignored by Git.
Only curated portable evidence under `docs/results/` belongs in the public repo.
