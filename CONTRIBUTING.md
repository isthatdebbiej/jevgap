# Contributing

The current testing scope is GaP, CaP-X, ASPIRE and ENPIRE across all 13 tasks.
Keep shared task definitions and evaluation criteria consistent across harnesses;
document differences in native workflows, readiness and resource enforcement.
See the [testing plan](task_suite/TESTING_PLAN.md) and [harness guide](task_suite/HARNESSES.md).

For the task suite, use Python 3.12, install `./task_suite[native,se3]`, obtain the
pinned GaP checkout and run `python scripts/check_tasks.py`. It has a separate
offline CI job. Upstream harnesses use their own environments; see
[coordinator setup](task_suite/SETUP.md) and the harness guide for prerequisites.

For the historical A/B and Rust-executor work, use Ubuntu 24.04, Python 3.12.3
and the pinned Rust toolchain. Run `bash scripts/setup.sh` then `bash scripts/check.sh`.
CI never makes billable API requests. Live experiments require an explicit `--live` flag.

Agents must ask the user for approval before any run that spends OpenAI API
credits, including calls made through an upstream harness. A configured key or
`--live` flag does not replace that approval. Documentation edits and offline
checks must not make paid model calls.

Keep changes focused. Explain the behavior change and validation in a pull request.
For scheduler changes, compare observable node inputs, invocation counts, decisions
and outputs against native GaP. Unsupported graph constructs must fail explicitly.
For historical A/B changes, keep the two observation schemas, controller and
admission behavior identical.

Do not check in credentials, private paths, camera recordings, machine inventories,
provider billing ledgers or raw unreviewed runs. Local output belongs in `results/`
or an external directory. Run `python scripts/privacy_check.py` before publishing.
It is a basic check, not a complete secret-detection system.

Preserve raw runs locally; publish selected evidence with sample counts, outcome
definitions, model versions and simulation assumptions. Do not discard failures or
present one episode as a statistical performance claim. Re-render rather than edit
timing overlays manually.

Contributions are licensed under Apache-2.0, the project license. Upstream GaP and
I2RT code retain their own notices and licenses. Do not modify vendored checkouts as
part of a benchmark without explicitly documenting and pinning the change.

Documentation should describe all four harnesses as the current study scope,
while distinguishing implemented adapters, validated task ports and remaining
development workflows. Preserve historical experiments and their results with
explicit scope labels.
