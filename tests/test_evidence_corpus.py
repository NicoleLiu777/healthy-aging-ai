import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_EVIDENCE_PATH
from app.models.evidence import EvidenceRecord
from app.repositories.evidence_repository import EvidenceRepository
from app.services.retrieval import retrieve_relevant_evidence

PRODUCTION_IDS = {
    "marziali-2024",
    "li-2023",
    "who-2025",
    "loveys-2019",
    "welch-2023-egm",
    "dino-2025",
}


def test_all_production_records_load_successfully(production_repository):
    records = production_repository.list_all()

    assert len(records) == 6
    assert {record.id for record in records} == PRODUCTION_IDS


def test_production_has_six_unique_ids(production_repository):
    records = production_repository.list_all()
    assert len({record.id for record in records}) == 6


def test_production_urls_and_verification_fields_present(production_repository):
    for record in production_repository.list_all():
        assert str(record.url)
        assert record.verification_status == "verified"
        assert record.verified_against
        assert str(record.verified_against[0])


def test_production_has_exactly_three_decision_eligible_records(production_repository):
    eligible = [record for record in production_repository.list_all() if record.decision_eligible]

    assert len(eligible) == 3
    assert {record.id for record in eligible} == {"marziali-2024", "li-2023", "dino-2025"}


def test_schema_requires_effectiveness_role_for_decision_eligible():
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "id": "invalid-001",
                "title": "Invalid record",
                "authors": ["Test Author"],
                "year": 2024,
                "url": "https://example.org/invalid-001",
                "topic": ["test"],
                "population": "Test population",
                "study_type": "Test study",
                "sample_size": None,
                "intervention": "Test intervention",
                "comparison": None,
                "outcomes_improved": [],
                "outcomes_not_improved": [],
                "source_role": "context",
                "decision_eligible": True,
                "evidence_strength": "limited",
                "evidence_strength_rationale": "Invalid combination",
                "limitations": [],
                "verification_status": "verified",
                "verified_against": ["https://example.org/invalid-001"],
            }
        )


def test_schema_requires_null_strength_when_not_decision_eligible():
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "id": "invalid-002",
                "title": "Invalid record",
                "authors": ["Test Author"],
                "year": 2024,
                "url": "https://example.org/invalid-002",
                "topic": ["test"],
                "population": "Test population",
                "study_type": "Test study",
                "sample_size": None,
                "intervention": "Test intervention",
                "comparison": None,
                "outcomes_improved": [],
                "outcomes_not_improved": [],
                "source_role": "context",
                "decision_eligible": False,
                "evidence_strength": "limited",
                "evidence_strength_rationale": "Invalid combination",
                "limitations": [],
                "verification_status": "verified",
                "verified_against": ["https://example.org/invalid-002"],
            }
        )


def test_schema_rejects_non_positive_counts():
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "id": "invalid-003",
                "title": "Invalid record",
                "authors": ["Test Author"],
                "year": 2024,
                "url": "https://example.org/invalid-003",
                "topic": ["test"],
                "population": "Test population",
                "study_type": "Test study",
                "sample_size": 0,
                "intervention": "Test intervention",
                "comparison": None,
                "outcomes_improved": [],
                "outcomes_not_improved": [],
                "source_role": "effectiveness",
                "decision_eligible": True,
                "evidence_strength": "limited",
                "evidence_strength_rationale": "Invalid count",
                "limitations": [],
                "verification_status": "verified",
                "verified_against": ["https://example.org/invalid-003"],
            }
        )


def test_schema_rejects_outcome_claims_on_non_effectiveness_records():
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "id": "invalid-004",
                "title": "Invalid context record",
                "authors": ["Test Author"],
                "year": 2024,
                "url": "https://example.org/invalid-004",
                "topic": ["policy"],
                "population": "General population",
                "study_type": "Policy report",
                "sample_size": None,
                "intervention": "Policy guidance",
                "comparison": None,
                "outcomes_improved": ["Depression symptoms"],
                "outcomes_not_improved": [],
                "source_role": "context",
                "decision_eligible": False,
                "evidence_strength": None,
                "evidence_strength_rationale": "Context source",
                "limitations": [],
                "verification_status": "verified",
                "verified_against": ["https://example.org/invalid-004"],
            }
        )


def test_schema_rejects_verified_records_without_verified_against():
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "id": "invalid-005",
                "title": "Invalid verified record",
                "authors": ["Test Author"],
                "year": 2024,
                "url": "https://example.org/invalid-005",
                "topic": ["test"],
                "population": "Test population",
                "study_type": "Test study",
                "sample_size": None,
                "intervention": "Test intervention",
                "comparison": None,
                "outcomes_improved": [],
                "outcomes_not_improved": [],
                "source_role": "context",
                "decision_eligible": False,
                "evidence_strength": None,
                "evidence_strength_rationale": "Context source",
                "limitations": [],
                "verification_status": "verified",
                "verified_against": [],
            }
        )


def test_production_non_effectiveness_records_have_empty_outcomes(production_repository):
    non_effectiveness = [
        record
        for record in production_repository.list_all()
        if record.source_role != "effectiveness"
    ]

    assert len(non_effectiveness) == 3
    for record in non_effectiveness:
        assert record.outcomes_improved == []
        assert record.outcomes_not_improved == []


def test_context_only_retrieval_produces_insufficient_evidence(production_client):
    response = production_client.post(
        "/api/ask",
        json={"question": "WHO social connection policy framing guidance"},
    )

    assert response.status_code == 200
    brief = response.json()
    assert brief["evidence_strength"] == "insufficient"
    assert brief["pilot_recommendation"] == "insufficient_evidence"


def test_mixed_retrieval_citations_are_subset_of_retrieved_records(
    production_client,
    production_repository,
):
    question = "AI conversational agents depression distress older adults social connection policy"
    retrieved_ids = {
        record.id
        for record in retrieve_relevant_evidence(question, production_repository.list_all())
    }

    response = production_client.post("/api/ask", json={"question": question})
    brief = response.json()
    citation_ids = {citation["evidence_id"] for citation in brief["citations"]}

    assert retrieved_ids
    assert citation_ids <= retrieved_ids


def test_production_corpus_file_is_valid_json():
    raw = DEFAULT_EVIDENCE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) == 6
