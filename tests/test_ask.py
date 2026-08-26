import pytest

from app.repositories.evidence_repository import EvidenceRepository
from app.services.retrieval import retrieve_relevant_evidence


def test_relevant_question_retrieves_fixture_evidence(client):
    response = client.post(
        "/api/ask",
        json={"question": "AI陪伴工具是否值得在独居老人中试点？"},
    )

    assert response.status_code == 200
    brief = response.json()
    assert brief["evidence_strength"] != "insufficient"
    assert brief["pilot_recommendation"] != "insufficient_evidence"
    assert brief["insufficient_evidence_reason"] is None
    assert len(brief["citations"]) >= 1
    assert brief["citations"][0]["evidence_id"] == "fixture-companion-ai-001"


def test_unrelated_question_triggers_insufficient_evidence(client):
    response = client.post(
        "/api/ask",
        json={"question": "What is the capital of France?"},
    )

    assert response.status_code == 200
    brief = response.json()
    assert brief["evidence_strength"] == "insufficient"
    assert brief["pilot_recommendation"] == "insufficient_evidence"
    assert brief["citations"] == []
    assert brief["insufficient_evidence_reason"] is not None


def test_citations_are_subset_of_retrieved_evidence_ids(client, fixture_evidence_path):
    question = "Should we pilot AI companion tools for older adults living alone?"
    repository = EvidenceRepository(fixture_evidence_path)
    retrieved_ids = {
        record.id
        for record in retrieve_relevant_evidence(question, repository.list_all())
    }

    response = client.post("/api/ask", json={"question": question})

    assert response.status_code == 200
    brief = response.json()
    citation_ids = {citation["evidence_id"] for citation in brief["citations"]}

    assert citation_ids
    assert citation_ids <= retrieved_ids


def test_companion_question_cites_companion_not_exercise(client):
    question = "AI陪伴工具是否值得在独居老人中试点？"

    response = client.post("/api/ask", json={"question": question})

    assert response.status_code == 200
    brief = response.json()
    citation_ids = {citation["evidence_id"] for citation in brief["citations"]}

    assert "fixture-companion-ai-001" in citation_ids
    assert "fixture-exercise-002" not in citation_ids


def test_decision_brief_includes_aggregated_outcomes(client):
    response = client.post(
        "/api/ask",
        json={"question": "AI companion loneliness medication adherence older adults"},
    )

    assert response.status_code == 200
    brief = response.json()
    assert "Self-reported loneliness scores" in brief["outcomes_improved"]
    assert "Medication adherence" in brief["outcomes_improved"]
    assert brief["pilot_recommendation"] == "pilot_with_safeguards"


def test_implementation_implications_are_not_returned_as_pilot_metrics(client):
    response = client.post(
        "/api/ask",
        json={"question": "AI companion loneliness medication adherence older adults"},
    )

    assert response.status_code == 200
    brief = response.json()

    assert "Monitor loneliness scores weekly" not in brief["pilot_metrics"]
    assert "Track medication adherence" not in brief["pilot_metrics"]
    assert "Self-reported loneliness scores" in brief["pilot_metrics"]
    assert "Hospitalization rate" in brief["pilot_metrics"]


@pytest.mark.parametrize(
    "question",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "abc"},
        {"question": "x" * 501},
    ],
)
def test_invalid_questions_return_422(client, question):
    response = client.post("/api/ask", json=question)

    assert response.status_code == 422
