import json
from pathlib import Path

import pytest

from app.services.retrieval import retrieve_relevant_evidence
from app.models.evidence import EvidenceRecord


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
