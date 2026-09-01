import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.evidence_v1 import EvidenceCorpusV1, EvidenceRecordV1


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_PATH = ROOT / "data/examples/evidence_records_v1.json"


def _example_corpus() -> dict:
    return json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))


def test_v1_examples_validate_and_cover_effectiveness_and_context_roles():
    corpus = EvidenceCorpusV1.model_validate(_example_corpus())

    assert len(corpus.records) == 2
    assert {record.source_role for record in corpus.records} == {
        "effectiveness",
        "context",
    }
    dino = next(record for record in corpus.records if "dino" in record.record_id)
    narrative = next(
        claim for claim in dino.claims if claim.claim_id == "claim-dino-narrative-finding"
    )
    assert narrative.study_count == 15
    assert "Thirteen of 15" in narrative.text
    assert narrative.decision_eligible is True


def test_schema_has_exactly_three_approved_themes():
    schema = EvidenceRecordV1.model_json_schema()
    theme_schema = schema["properties"]["primary_theme"]

    assert theme_schema["enum"] == [
        "ai_conversational_agents_mental_health",
        "older_adult_digital_social_connection",
        "responsible_ai_companion_design",
    ]


def test_non_effectiveness_claim_cannot_be_decision_eligible():
    record = _example_corpus()["records"][1]
    record["claims"][0]["decision_eligible"] = True
    record["decision_eligible"] = True
    record["evidence_strength"] = "limited"

    with pytest.raises(ValidationError, match="decision-eligible claims require"):
        EvidenceRecordV1.model_validate(record)


def test_claims_must_reference_declared_source_locations():
    record = _example_corpus()["records"][0]
    record["claims"][0]["reference_ids"] = ["ref-does-not-exist"]

    with pytest.raises(ValidationError, match="unknown reference_ids"):
        EvidenceRecordV1.model_validate(record)


def test_record_eligibility_must_match_eligible_claims():
    record = _example_corpus()["records"][0]
    record["decision_eligible"] = False
    record["evidence_strength"] = None

    with pytest.raises(ValidationError, match="must match the presence"):
        EvidenceRecordV1.model_validate(record)


def test_verified_provenance_requires_verification_evidence():
    record = _example_corpus()["records"][0]
    record["provenance"]["verification_urls"] = []

    with pytest.raises(ValidationError, match="verified provenance requires"):
        EvidenceRecordV1.model_validate(record)


def test_v1_examples_are_not_loaded_into_active_production_corpus(
    production_repository,
):
    active_ids = {record.id for record in production_repository.list_all()}

    assert len(active_ids) == 6
    assert not any(record_id.endswith("-example") for record_id in active_ids)
