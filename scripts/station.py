"""Run a simulated evaluation station; observation-only shadow mode by default."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from rtbench.station.runner import Config, execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dispatch-sim", action="store_true")
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    summary = execute(Config(**json.loads(a.config.read_text())), a.output, a.dispatch_sim, a.live)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
