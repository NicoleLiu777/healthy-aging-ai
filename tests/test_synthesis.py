from app.models.evidence import EvidenceRecord
from app.services.synthesis import _aggregate_evidence_strength, synthesize_decision_brief


def _make_record(
    record_id: str,
    *,
    source_role: str = "effectiveness",
    decision_eligible: bool = True,
    evidence_strength: str | None = "moderate",
    outcomes_improved: list[str] | None = None,
    outcomes_not_improved: list[str] | None = None,
    implementation_implications: list[str] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord.model_validate(
        {
            "id": record_id,
            "title": f"Fixture {record_id}",
            "authors": ["Test Author"],
            "year": 2022,
            "url": f"https://example.org/fixtures/{record_id}",
            "doi": None,
            "topic": ["test"],
            "population": "Test population",
            "study_type": "Test study",
            "sample_size": 50,
            "included_studies": None,
            "intervention": "Test intervention",
            "comparison": None,
            "outcomes_improved": outcomes_improved or ["Outcome A"],
            "outcomes_not_improved": outcomes_not_improved or ["Outcome B"],
            "source_role": source_role,
            "decision_eligible": decision_eligible,
            "evidence_strength": evidence_strength,
            "evidence_strength_rationale": "Fixture rationale",
            "limitations": ["Test limitation"],
            "implementation_implications": implementation_implications or ["Track weekly"],
            "verification_status": "verified",
            "verified_against": [f"https://example.org/fixtures/{record_id}"],
        }
    )


def _make_context_record(record_id: str) -> EvidenceRecord:
    return EvidenceRecord.model_validate(
        {
            "id": record_id,
            "title": f"Fixture context {record_id}",
            "authors": ["Test Author"],
            "year": 2025,
            "url": f"https://example.org/fixtures/{record_id}",
            "doi": None,
            "topic": ["policy", "context"],
            "population": "General population",
            "study_type": "Policy report",
            "sample_size": None,
            "included_studies": None,
            "intervention": "Policy guidance",
            "comparison": None,
            "outcomes_improved": [],
            "outcomes_not_improved": [],
            "source_role": "context",
            "decision_eligible": False,
            "evidence_strength": None,
            "evidence_strength_rationale": "Context-only fixture",
            "limitations": [],
            "implementation_implications": ["Context only"],
            "verification_status": "verified",
            "verified_against": [f"https://example.org/fixtures/{record_id}"],
        }
    )


def test_aggregate_evidence_strength_uses_weakest_record():
    records = [
        _make_record("strong-001", evidence_strength="strong"),
        _make_record("moderate-001", evidence_strength="moderate"),
        _make_record("early-001", evidence_strength="early"),
    ]

    assert _aggregate_evidence_strength(records) == "early"


def test_synthesis_uses_conservative_aggregate_strength():
    records = [
        _make_record("strong-001", evidence_strength="strong"),
        _make_record("early-001", evidence_strength="early"),
    ]
    brief = synthesize_decision_brief("Test question with enough length", records)

    assert brief.evidence_strength == "early"
    assert brief.pilot_recommendation == "do_not_pilot"


def test_context_sources_do_not_affect_aggregate_strength():
    records = [
        _make_record("moderate-001", evidence_strength="moderate"),
        _make_context_record("context-001"),
    ]
    brief = synthesize_decision_brief("Test question with enough length", records)

    assert brief.evidence_strength == "moderate"
    assert brief.pilot_recommendation == "pilot_with_safeguards"


def test_context_only_retrieval_returns_insufficient_evidence():
    records = [_make_context_record("context-only-001")]
    brief = synthesize_decision_brief("Test question with enough length", records)

    assert brief.evidence_strength == "insufficient"
    assert brief.pilot_recommendation == "insufficient_evidence"
    assert brief.pilot_metrics == []
    assert len(brief.citations) == 1


def test_pilot_metrics_derived_from_outcomes_not_implementation_implications():
    records = [
        _make_record(
            "companion-001",
            outcomes_improved=["Self-reported loneliness scores", "Medication adherence"],
            outcomes_not_improved=["Hospitalization rate"],
            implementation_implications=[
                "Monitor loneliness scores weekly",
                "Track medication adherence",
            ],
        )
    ]
    brief = synthesize_decision_brief("Test question with enough length", records)

    assert "Self-reported loneliness scores" in brief.pilot_metrics
    assert "Medication adherence" in brief.pilot_metrics
    assert "Hospitalization rate" in brief.pilot_metrics
    assert "Monitor loneliness scores weekly" not in brief.pilot_metrics
    assert "Track medication adherence" not in brief.pilot_metrics
