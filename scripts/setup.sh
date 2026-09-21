#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
command -v cargo >/dev/null || { echo 'Install Rust: https://rustup.rs/'; exit 1; }
RTBENCH_ENV="${RTBENCH_ENV:-$HOME/.local/share/rtbench/yam-venv}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/.cache/rtbench/target}"
mkdir -p vendor
for repo in graph-as-policy i2rt; do
  if [ "$repo" = graph-as-policy ]; then
    url=https://github.com/graph-robots/graph-as-policy.git; pin=$(cat gap-commit.txt)
  else
    url=https://github.com/i2rt-robotics/i2rt.git; pin=$(cat i2rt-commit.txt)
  fi
  if [ ! -d "vendor/$repo/.git" ]; then
    git clone "$url" "vendor/$repo"
    git -C "vendor/$repo" checkout --detach "$pin"
  fi
  [ "$(git -C "vendor/$repo" rev-parse HEAD)" = "$pin" ] || { echo "$repo checkout differs from pin; refusing to overwrite it."; exit 1; }
  # Normalize CRLF when checking a checkout originally created by Windows Git.
  [ -z "$(git -c core.autocrlf=true -C "vendor/$repo" status --porcelain)" ] || { echo "$repo has local changes; refusing a misleading pinned build."; exit 1; }
done
[ -x "$RTBENCH_ENV/bin/python" ] || uv venv --python "$(cat .python-version)" "$RTBENCH_ENV"
uv pip sync --python "$RTBENCH_ENV/bin/python" requirements.lock
cargo build --release --locked
echo "Ready. Run: bash scripts/check.sh"
