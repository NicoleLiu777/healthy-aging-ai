from pathlib import Path

from evals.build_blinded_review_packet import BLINDED_SELECTION, build_packet


ROOT = Path(__file__).resolve().parents[1]


def test_blinded_packet_contains_fixed_nine_case_sample():
    packet = build_packet(
        ROOT / "evals/questions_v0.1.json",
        ROOT / "data/evidence.json",
    )

    assert len(BLINDED_SELECTION) == 9
    for label, _ in BLINDED_SELECTION:
        assert packet.count(f"## {label}\n") == 1


def test_blinded_packet_omits_gold_and_machine_scoring_fields():
    packet = build_packet(
        ROOT / "evals/questions_v0.1.json",
        ROOT / "data/evidence.json",
    )

    for _, case_id in BLINDED_SELECTION:
        assert case_id not in packet
    for forbidden in (
        "expected_evidence_ids",
        "answerability",
        "failure_class",
        "retrieval_hit_at_5",
        "abstention_correct",
        "machine pass",
    ):
        assert forbidden not in packet


def test_blinded_packet_preserves_reviewable_output_and_rubric_fields():
    packet = build_packet(
        ROOT / "evals/questions_v0.1.json",
        ROOT / "data/evidence.json",
    )

    assert "**Question:**" in packet
    assert "**Conclusion:**" in packet
    assert "**Citations:**" in packet
    assert "Usefulness | Traceability | Completeness | Risk control | Required edits" in packet
    assert packet.count("**Disposition:** accept / edit / reject") == 9
    assert "Reviewer sign-off" in packet
