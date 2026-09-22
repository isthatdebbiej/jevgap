import json
import pytest
from decision_eval import load_examples, score


def test_failures_count_against_accuracy_and_pairs_remain_matched():
    report = score(
        [
            dict(id="x", system="A", gold_decision="abort", decision="abort"),
            dict(id="x", system="B", gold_decision="abort", error_type="TimeoutError"),
            dict(id="y", system="B", gold_decision="replan", decision="replan"),
        ]
    )
    assert report["B"]["accuracy"] == 0.5
    assert report["B"]["invalid_or_failed"] == 1
    assert report["paired"] == {"n": 1, "A_only_correct": 1, "B_only_correct": 0}


def test_duplicate_ids_and_missing_provenance_rejected(tmp_path):
    p = tmp_path / "states.jsonl"
    row = dict(id="1", episode_id="episode1", gold_decision="continue", state={}, provenance="hand-labeled")
    p.write_text(json.dumps(row) + "\n" + json.dumps(row))
    with pytest.raises(ValueError):
        load_examples(p)
    del row["provenance"]
    p.write_text(json.dumps(row))
    with pytest.raises(ValueError):
        load_examples(p)
