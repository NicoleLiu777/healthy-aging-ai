import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.validate_source_review_packet import SourceReviewPacket, validate_packet
from scripts.render_nicole_completion_checklist import OUTPUT, render


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
REGISTER = ROOT / "data/staging/phase-b/source-register.json"
LICENCE_REPORT = ROOT / "evals/reviews/phase_b_licence_verification_2026-09-09.json"


def load():
    packet = SourceReviewPacket.model_validate_json(PACKET.read_text())
    register = json.loads(REGISTER.read_text())
    return packet, register


def test_review_packet_covers_every_registered_batch_candidate():
    packet, register = load()
    validate_packet(packet, register, final=False)
    assert len(packet.decisions) == 22
    assert packet.status == "partially_reviewed"
    assert sum(item.disposition is not None for item in packet.decisions) == 20
    assert {item.candidate_id for item in packet.decisions if item.disposition is None} == {
        "technology-loneliness-2026",
        "prism2-2024",
    }


def test_draft_packet_cannot_pass_final_gate():
    packet, register = load()
    with pytest.raises(ValueError, match="complete status"):
        validate_packet(packet, register, final=True)


def test_edit_requires_replacement_claims():
    packet, _ = load()
    raw = packet.decisions[0].model_dump(mode="json")
    raw["disposition"] = "edit"
    with pytest.raises(ValidationError, match="edited_claims"):
        type(packet.decisions[0]).model_validate(raw)


def test_non_effectiveness_source_cannot_receive_strength():
    packet, _ = load()
    item = next(x for x in packet.decisions if x.proposed_source_role != "effectiveness")
    raw = item.model_dump(mode="json")
    raw["evidence_strength"] = "limited"
    with pytest.raises(ValidationError, match="only effectiveness"):
        type(item).model_validate(raw)


def test_nicole_checklist_is_deterministic_and_complete():
    packet, _ = load()
    rendered = render()
    assert rendered == OUTPUT.read_text()
    for item in packet.decisions:
        assert f" {item.candidate_id} —" in rendered
    assert "Close the eight-source first review" in rendered
    assert "Final answer review and exact release approval" in rendered


def test_nicole_strengths_are_bound_to_batch4_claims():
    batch = json.loads(
        (ROOT / "data/staging/phase-b/batch4-reviewed-sources.json").read_text()
    )
    expected = {
        "10.2196/43862": "moderate",
        "10.2196/mental.7785": "limited",
        "10.2196/12106": "early",
        "10.2196/26771": "early",
    }
    actual = {
        source["doi"]: source["evidence_strength"]
        for source in batch["sources"]
        if source["doi"] in expected
    }
    assert actual == expected
    for source in batch["sources"]:
        if source["doi"] in expected:
            assert source["decision_eligible"] is True
            assert all(claim["decision_eligible"] for claim in source["claims"])


def test_heinz_restriction_and_correspondence_are_preserved():
    packet, _ = load()
    heinz = next(x for x in packet.decisions if x.candidate_id == "heinz-2025")
    assert heinz.licence_status == "restricted"
    review = json.loads(
        (ROOT / "evals/reviews/phase_b_source_review_2026-09-08.json").read_text()
    )
    assert {item["doi"].lower() for item in review["heinz_correspondence"]} == {
        "10.1056/aip2500390",
        "10.1056/aip2500453",
        "10.1056/aip2500680",
    }


def test_source_specific_licence_checks_are_machine_readable_and_applied():
    packet, register = load()
    report = json.loads(LICENCE_REPORT.read_text())
    verified = {item["candidate_id"]: item for item in report["records"]}
    assert len(verified) == 10
    assert all(item["verification_level"] == "publisher_page" for item in verified.values())

    packet_by_id = {item.candidate_id: item for item in packet.decisions}
    register_by_id = {item["candidate_id"]: item for item in register["sources"]}
    for candidate_id, result in verified.items():
        assert result["licence_status"] == "permitted"
        assert packet_by_id[candidate_id].licence_status == "permitted"
        assert register_by_id[candidate_id]["licence"] == result["licence"]
        assert register_by_id[candidate_id]["licence_evidence_url"] == result["evidence_url"]
