import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api.routes.ask import router as ask_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.health import router as health_router
from app.core.config import DEFAULT_EVIDENCE_PATH, Settings
from app.repositories.evidence_repository import EvidenceRepository

DEPLOYMENT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "https://suvane.org,"
    "https://www.suvane.org,"
    "https://suvane-research.oliviaralph89.chatgpt.site"
)
ALLOWED_ORIGIN = "https://suvane.org"
DISALLOWED_ORIGIN = "https://evil.example.com"


def _build_deployment_app(cors_origins: str = DEPLOYMENT_CORS_ORIGINS) -> FastAPI:
    settings = Settings(cors_origins=cors_origins)
    deployment_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )
    deployment_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    deployment_app.include_router(health_router)
    deployment_app.include_router(evidence_router)
    deployment_app.include_router(ask_router)
    return deployment_app


@pytest.fixture
def deployment_client() -> TestClient:
    return TestClient(_build_deployment_app())


def test_health_returns_200(deployment_client):
    response = deployment_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_allowed_origin_preflight_includes_access_control_allow_origin(deployment_client):
    response = deployment_client.options(
        "/api/ask",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_disallowed_origin_preflight_does_not_include_access_control_allow_origin(
    deployment_client,
):
    response = deployment_client.options(
        "/api/ask",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_comma_separated_cors_origins_are_trimmed():
    settings = Settings(
        cors_origins=(
            "http://localhost:5173, https://suvane.org ,"
            "https://www.suvane.org,https://suvane-research.oliviaralph89.chatgpt.site"
        )
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://suvane.org",
        "https://www.suvane.org",
        "https://suvane-research.oliviaralph89.chatgpt.site",
    ]


def test_production_evidence_corpus_still_loads():
    repository = EvidenceRepository(DEFAULT_EVIDENCE_PATH)

    records = repository.list_all()

    assert len(records) == 6


def test_ask_returns_decision_brief(production_client):
    response = production_client.post(
        "/api/ask",
        json={"question": "Should we pilot AI conversational agents for older adults?"},
    )

    assert response.status_code == 200
    brief = response.json()
    assert brief["question"]
    assert brief["conclusion"]
    assert brief["evidence_strength"]
    assert "pilot_recommendation" in brief
    assert "citations" in brief
