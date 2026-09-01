import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_day7_human_review_is_complete_and_scores_are_bounded():
    review = json.loads(
        (ROOT / "evals/reviews/day7_human_review_results_v0.1.json").read_text(
            encoding="utf-8"
        )
    )

    assert review["status"] == "complete"
    assert review["sample_size"] == review["completed_count"] == 9
    assert len(review["reviews"]) == 9
    assert len({item["blinded_label"] for item in review["reviews"]}) == 9
    for item in review["reviews"]:
        assert set(item["scores"]) == {
            "usefulness",
            "traceability",
            "completeness",
            "risk_control",
            "required_edits",
        }
        assert all(1 <= score <= 5 for score in item["scores"].values())
        assert item["disposition"] in {"accept", "edit", "reject"}


def test_day7_human_review_aggregate_matches_case_records():
    review = json.loads(
        (ROOT / "evals/reviews/day7_human_review_results_v0.1.json").read_text(
            encoding="utf-8"
        )
    )
    items = review["reviews"]

    means = {
        dimension: round(sum(item["scores"][dimension] for item in items) / len(items), 2)
        for dimension in items[0]["scores"]
    }
    dispositions = {
        disposition: sum(item["disposition"] == disposition for item in items)
        for disposition in ("accept", "edit", "reject")
    }

    assert review["aggregate"]["mean_scores"] == means
    assert review["aggregate"]["dispositions"] == dispositions
    assert review["aggregate"]["risk_flags"] == sum(
        item["risk_flag"] for item in items
    )
