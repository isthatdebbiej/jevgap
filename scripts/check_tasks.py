"""Offline task integration checks; missing pinned dependencies fail explicitly."""
import logging
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("GAP_ROOT", str(ROOT / "vendor/graph-as-policy"))
sys.path.insert(0, str(ROOT / "task_suite"))

from rtbench_tasks.config import GAP_COMMIT, gap_revision


def main():
    gap = Path(os.environ["GAP_ROOT"])
    if gap_revision(gap) != GAP_COMMIT or (ROOT / "gap-commit.txt").read_text().strip() != GAP_COMMIT:
        raise RuntimeError("task suite and graph-as-policy pin differ")
    # Test runs generate identical skill modules in multiple temp directories.
    # GaP warns on rediscovery; all other errors still surface as test failures.
    logging.getLogger("gap.skills").setLevel(logging.ERROR)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "task_suite/tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
