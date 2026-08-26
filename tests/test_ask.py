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


def test_citations_reference_retrieved_evidence(client, fixture_records):
    response = client.post(
        "/api/ask",
        json={"question": "Should we pilot AI companion tools for older adults living alone?"},
    )

    assert response.status_code == 200
    brief = response.json()
    valid_ids = {record.id for record in fixture_records}

    assert brief["citations"]
    for citation in brief["citations"]:
        assert citation["evidence_id"] in valid_ids
        assert citation["supported_claims"]


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
