import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.validate_source_review_packet import SourceReviewPacket, validate_packet
from scripts.render_nicole_completion_checklist import OUTPUT, render


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evals/reviews/phase_b_remaining_source_review_template.json"
REGISTER = ROOT / "data/staging/phase-b/source-register.json"


def load():
    packet = SourceReviewPacket.model_validate_json(PACKET.read_text())
    register = json.loads(REGISTER.read_text())
    return packet, register


def test_review_packet_covers_every_and_only_pending_candidate():
    packet, register = load()
    validate_packet(packet, register, final=False)
    assert len(packet.decisions) == 22
    assert packet.status == "draft_pending_human_review"
    assert all(item.disposition is None for item in packet.decisions)


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
