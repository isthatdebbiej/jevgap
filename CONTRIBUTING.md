# Contributing

Use Ubuntu 24.04, Python 3.12.3 and the pinned Rust toolchain. Run `bash scripts/setup.sh`
then `bash scripts/check.sh`. CI uses deterministic local workers and never makes
billable API requests. Live experiments require an explicit `--live` flag.

Keep changes focused. Explain the behavior change and validation in a pull request.
For scheduler changes, compare observable node inputs, invocation counts, decisions
and outputs against native GaP. Unsupported graph constructs must fail explicitly.
Keep A and B's observation schemas, controller and admission behavior identical.

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
