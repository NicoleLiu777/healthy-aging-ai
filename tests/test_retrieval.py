import json
from pathlib import Path

import pytest

from app.models.evidence import EvidenceRecord
from app.services.retrieval import retrieve_relevant_evidence, score_record, tokenize


def test_retrieve_relevant_evidence_with_keywords(fixture_records):
    results = retrieve_relevant_evidence(
        "AI companion tools for older adults living alone",
        fixture_records,
    )

    assert len(results) >= 1
    assert results[0].id == "fixture-companion-ai-001"


def test_retrieve_returns_empty_for_unrelated_question(fixture_records):
    results = retrieve_relevant_evidence(
        "quantum computing hardware architecture",
        fixture_records,
    )

    assert results == []


def test_retrieve_rejects_top_k_below_one(fixture_records):
    with pytest.raises(ValueError, match="top_k must be at least 1"):
        retrieve_relevant_evidence("AI companion", fixture_records, top_k=0)


def test_retrieve_enforces_top_k(fixture_records):
    extra_records = [
        EvidenceRecord.model_validate(
            {
                **{
                    "id": f"fixture-companion-ai-{index:03d}",
                    "title": f"Fixture study {index}: AI companion tools for older adults",
                    "authors": ["Test Author"],
                    "year": 2020 + index,
                    "url": f"https://example.org/fixtures/companion-ai-{index:03d}",
                    "topic": ["AI companion", "older adults", "social isolation"],
                    "population": "Community-dwelling older adults living alone",
                    "study_type": "Pilot",
                    "sample_size": 100,
                    "intervention": "AI companion assistant",
                    "comparison": "Usual care",
                    "outcomes_improved": ["Loneliness scores"],
                    "outcomes_not_improved": [],
                    "evidence_strength": "moderate",
                    "limitations": [],
                    "implementation_implications": [],
                }
            }
        )
        for index in range(1, 8)
    ]
    records = fixture_records + extra_records

    results = retrieve_relevant_evidence(
        "AI companion tools for older adults living alone",
        records,
        top_k=3,
    )

    assert len(results) == 3


def test_retrieve_orders_newer_studies_first_on_score_tie():
    shared = {
        "authors": ["Test Author"],
        "url": "https://example.org/fixtures/tie",
        "topic": ["AI companion", "older adults"],
        "population": "Older adults",
        "study_type": "Pilot",
        "sample_size": 100,
        "intervention": "AI companion assistant",
        "comparison": None,
        "outcomes_improved": ["Loneliness scores"],
        "outcomes_not_improved": [],
        "evidence_strength": "moderate",
        "limitations": [],
        "implementation_implications": [],
    }
    older = EvidenceRecord.model_validate(
        {
            **shared,
            "id": "fixture-older",
            "title": "Older AI companion study",
            "year": 2019,
        }
    )
    newer = EvidenceRecord.model_validate(
        {
            **shared,
            "id": "fixture-newer",
            "title": "Newer AI companion study",
            "year": 2024,
        }
    )

    results = retrieve_relevant_evidence(
        "AI companion older adults",
        [older, newer],
    )

    assert [record.id for record in results] == ["fixture-newer", "fixture-older"]


def test_retrieve_uses_evidence_id_as_final_tiebreaker():
    shared = {
        "authors": ["Test Author"],
        "year": 2022,
        "url": "https://example.org/fixtures/tie",
        "topic": ["AI companion", "older adults"],
        "population": "Older adults",
        "study_type": "Pilot",
        "sample_size": 100,
        "intervention": "AI companion assistant",
        "comparison": None,
        "outcomes_improved": ["Loneliness scores"],
        "outcomes_not_improved": [],
        "evidence_strength": "moderate",
        "limitations": [],
        "implementation_implications": [],
    }
    record_b = EvidenceRecord.model_validate(
        {**shared, "id": "fixture-b", "title": "AI companion study B"}
    )
    record_a = EvidenceRecord.model_validate(
        {**shared, "id": "fixture-a", "title": "AI companion study A"}
    )

    results = retrieve_relevant_evidence(
        "AI companion older adults",
        [record_b, record_a],
    )

    assert [record.id for record in results] == ["fixture-a", "fixture-b"]


def test_repeated_query_words_do_not_inflate_relevance(fixture_records):
    baseline = retrieve_relevant_evidence(
        "AI companion older adults",
        fixture_records,
    )
    repeated = retrieve_relevant_evidence(
        "AI AI AI companion companion older adults adults",
        fixture_records,
    )

    assert [record.id for record in baseline] == [record.id for record in repeated]
    baseline_score, baseline_matches = score_record(
        fixture_records[0],
        tokenize("AI companion older adults"),
    )
    repeated_score, repeated_matches = score_record(
        fixture_records[0],
        tokenize("AI AI AI companion companion older adults adults"),
    )
    assert baseline_score == repeated_score
    assert baseline_matches == repeated_matches


def test_unrelated_chinese_aging_question_does_not_match_companion_fixture(fixture_records):
    results = retrieve_relevant_evidence(
        "老人饮食应该注意什么",
        fixture_records,
    )

    assert results == []


def test_chinese_companion_question_still_retrieves_companion_fixture(fixture_records):
    results = retrieve_relevant_evidence(
        "AI陪伴工具是否值得在独居老人中试点？",
        fixture_records,
    )

    assert len(results) >= 1
    assert results[0].id == "fixture-companion-ai-001"


def test_empty_corpus_returns_insufficient(client, tmp_path: Path):
    empty_path = tmp_path / "empty-evidence.json"
    empty_path.write_text(json.dumps([]), encoding="utf-8")

    from app.core.config import Settings, get_settings
    from app.dependencies import clear_dependency_caches, get_evidence_repository
    from app.main import app
    from app.repositories.evidence_repository import EvidenceRepository
    from fastapi.testclient import TestClient

    clear_dependency_caches()
    get_settings.cache_clear()

    app.dependency_overrides[get_settings] = lambda: Settings(evidence_path=empty_path)
    app.dependency_overrides[get_evidence_repository] = lambda: EvidenceRepository(
        empty_path
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/ask",
            json={"question": "AI companion tools for older adults"},
        )
        brief = response.json()
        assert brief["evidence_strength"] == "insufficient"
        assert brief["citations"] == []

    app.dependency_overrides.clear()
    clear_dependency_caches()
