#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
RTBENCH_ENV="${RTBENCH_ENV:-$HOME/.local/share/rtbench/yam-venv}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/.cache/rtbench/target}"
export RTBENCH_BINARY="$CARGO_TARGET_DIR/release/rtbench-runtime"
cargo test --locked
cargo build --release --locked
"$RTBENCH_ENV/bin/python" -m pytest -q
RTBENCH_CHECK_DIR=$(mktemp -d)
trap 'rm -rf -- "$RTBENCH_CHECK_DIR"' EXIT
"$RTBENCH_ENV/bin/python" scripts/executors.py --diagnostic "$RTBENCH_CHECK_DIR/conformance"
"$RTBENCH_ENV/bin/python" scripts/privacy_check.py
