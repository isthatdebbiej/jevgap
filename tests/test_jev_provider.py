import concurrent.futures
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jev_provider as j


def test_parallel_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(j, "CAP", 0.0091)

    def attempt(_):
        try:
            j.reserve(tmp_path / "budget.sqlite")
            return True
        except RuntimeError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 3


def test_pinned_contract():
    assert j.MODEL == "jev-1.13.0"
    assert j.RESERVATION > 64000 * j.RATE
    assert set(j.CRITERIA) == {"continue", "reperceive", "replan", "abort"}
