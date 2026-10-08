"""Repository-root entry point for the configured native GaP task experiments."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task_suite"))

from rtbench_tasks.experiment import main

if __name__ == "__main__":
    raise SystemExit(main())
