import pytest
from fastapi.testclient import TestClient

from app.core.config import DEFAULT_EVIDENCE_PATH, Settings
from app.main import create_app
from app.repositories.evidence_repository import EvidenceRepository

DEPLOYMENT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "https://suvane.org,"
    "https://www.suvane.org,"
    "https://suvane-research.oliviaralph89.chatgpt.site"
)
ALLOWED_ORIGIN = "https://suvane.org"
DISALLOWED_ORIGIN = "https://evil.example.com"


@pytest.fixture
def deployment_client() -> TestClient:
    return TestClient(create_app(Settings(cors_origins=DEPLOYMENT_CORS_ORIGINS)))


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
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert response.headers.get("access-control-allow-methods") == "GET, POST, OPTIONS"
    assert response.headers.get("access-control-allow-headers") == (
        "Accept, Accept-Language, Content-Language, Content-Type"
    )


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


@pytest.mark.parametrize("path", ["/health", "/api/evidence"])
def test_security_headers_are_present(deployment_client, path):
    response = deployment_client.get(path)

    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


def test_ask_disables_response_caching(deployment_client):
    response = deployment_client.post(
        "/api/ask",
        json={"question": "Should we pilot AI conversational agents for older adults?"},
    )

    assert response.headers["cache-control"] == "no-store"


def test_evidence_query_rejects_more_than_200_characters(deployment_client):
    response = deployment_client.get("/api/evidence", params={"q": "x" * 201})

    assert response.status_code == 422
    assert response.headers["x-content-type-options"] == "nosniff"


def test_request_body_limit_rejects_oversized_json(deployment_client):
    response = deployment_client.post(
        "/api/ask",
        content=b'{' + (b'"padding":"' + b"x" * 8192 + b'"}'),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds 8192 bytes"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_production_docs_can_be_disabled():
    client = TestClient(
        create_app(
            Settings(
                cors_origins=DEPLOYMENT_CORS_ORIGINS,
                api_docs_enabled=False,
            )
        )
    )

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_local_docs_remain_available():
    client = TestClient(create_app(Settings(api_docs_enabled=True)))

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
