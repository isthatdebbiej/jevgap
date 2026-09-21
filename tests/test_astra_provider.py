import concurrent.futures
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import astra_provider as a
import jev_provider as j


def test_shared_decision_contract():
    assert a.CRITERIA == j.CRITERIA
    assert a.INSTRUCTIONS == j.INSTRUCTIONS
    assert a.RESERVATION > 18000 * 12.5 / 1e6 + 2048 * 50 / 1e6


def test_concurrent_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "CAP", 1.051)

    def attempt(_):
        try:
            a.reserve(tmp_path / "ledger.sqlite")
            return True
        except RuntimeError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 3
