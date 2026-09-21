#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
RTBENCH_ENV="${RTBENCH_ENV:-$HOME/.local/share/rtbench/yam-venv}"
export PYTHONPATH="$PWD/vendor/i2rt${PYTHONPATH:+:$PYTHONPATH}"
# Explicit --sim matters: upstream defaults to hardware.
exec "$RTBENCH_ENV/bin/python" vendor/i2rt/examples/minimum_gello/minimum_gello.py \
  --mode visualizer_local --sim --arm yam --gripper linear_4310
