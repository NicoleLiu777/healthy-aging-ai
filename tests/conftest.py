import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import DEFAULT_EVIDENCE_PATH, Settings, get_settings
from app.dependencies import clear_dependency_caches, get_evidence_repository
from app.main import app
from app.models.evidence import EvidenceRecord
from app.repositories.evidence_repository import EvidenceRepository

FIXTURE_EVIDENCE: list[dict[str, object]] = [
    {
        "id": "fixture-companion-ai-001",
        "title": "Fixture study: AI companion tools for older adults living alone",
        "authors": ["Test Author A", "Test Author B"],
        "year": 2023,
        "url": "https://example.org/fixtures/companion-ai-001",
        "doi": None,
        "topic": ["AI companion", "older adults", "social isolation", "独居老人"],
        "population": "Community-dwelling older adults living alone",
        "study_type": "Randomized controlled pilot",
        "sample_size": 120,
        "included_studies": None,
        "intervention": "AI companion voice assistant with daily check-ins",
        "comparison": "Usual care",
        "outcomes_improved": ["Self-reported loneliness scores", "Medication adherence"],
        "outcomes_not_improved": ["Hospitalization rate"],
        "source_role": "effectiveness",
        "decision_eligible": True,
        "evidence_strength": "moderate",
        "evidence_strength_rationale": "Fixture effectiveness record for isolated tests.",
        "limitations": ["Short follow-up period", "Single-site pilot"],
        "implementation_implications": [
            "Monitor loneliness scores weekly",
            "Track medication adherence",
        ],
        "verification_status": "verified",
        "verified_against": ["https://example.org/fixtures/companion-ai-001"],
    },
    {
        "id": "fixture-exercise-002",
        "title": "Fixture study: Structured walking program for sedentary seniors",
        "authors": ["Test Author C"],
        "year": 2021,
        "url": "https://example.org/fixtures/exercise-002",
        "doi": None,
        "topic": ["exercise", "walking", "mobility"],
        "population": "Sedentary adults aged 65+",
        "study_type": "Observational cohort",
        "sample_size": 80,
        "included_studies": None,
        "intervention": "12-week supervised walking program",
        "comparison": None,
        "outcomes_improved": ["6-minute walk distance"],
        "outcomes_not_improved": ["Cognitive function"],
        "source_role": "effectiveness",
        "decision_eligible": True,
        "evidence_strength": "limited",
        "evidence_strength_rationale": "Fixture effectiveness record for isolated tests.",
        "limitations": ["No control group"],
        "implementation_implications": ["Track walking distance at baseline and week 12"],
        "verification_status": "verified",
        "verified_against": ["https://example.org/fixtures/exercise-002"],
    },
    {
        "id": "fixture-context-003",
        "title": "Fixture context source on social connection policy",
        "authors": ["Test Policy Author"],
        "year": 2025,
        "url": "https://example.org/fixtures/context-003",
        "doi": None,
        "topic": ["social connection", "policy", "loneliness"],
        "population": "General populations",
        "study_type": "Policy context report",
        "sample_size": None,
        "included_studies": None,
        "intervention": "Policy guidance on social connection",
        "comparison": None,
        "outcomes_improved": [],
        "outcomes_not_improved": [],
        "source_role": "context",
        "decision_eligible": False,
        "evidence_strength": None,
        "evidence_strength_rationale": "Fixture context record for role-separation tests.",
        "limitations": [],
        "implementation_implications": ["Use only for contextual framing"],
        "verification_status": "verified",
        "verified_against": ["https://example.org/fixtures/context-003"],
    },
]


@pytest.fixture
def fixture_evidence_path(tmp_path: Path) -> Path:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(FIXTURE_EVIDENCE), encoding="utf-8")
    return evidence_path


@pytest.fixture
def fixture_records() -> list[EvidenceRecord]:
    return [EvidenceRecord.model_validate(item) for item in FIXTURE_EVIDENCE]


@pytest.fixture
def client(fixture_evidence_path: Path) -> Generator[TestClient, None, None]:
    clear_dependency_caches()
    get_settings.cache_clear()

    def override_settings() -> Settings:
        return Settings(evidence_path=fixture_evidence_path)

    def override_repository() -> EvidenceRepository:
        return EvidenceRepository(fixture_evidence_path)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_evidence_repository] = override_repository

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    clear_dependency_caches()


@pytest.fixture
def production_repository() -> EvidenceRepository:
    return EvidenceRepository(DEFAULT_EVIDENCE_PATH)


@pytest.fixture
def production_client() -> Generator[TestClient, None, None]:
    clear_dependency_caches()
    get_settings.cache_clear()

    def override_settings() -> Settings:
        return Settings(evidence_path=DEFAULT_EVIDENCE_PATH)

    def override_repository() -> EvidenceRepository:
        return EvidenceRepository(DEFAULT_EVIDENCE_PATH)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_evidence_repository] = override_repository

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    clear_dependency_caches()
