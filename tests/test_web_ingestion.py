import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.ingestion.web import (
    MAX_RESPONSE_BYTES,
    WebExtractionBatch,
    WebExtractionError,
    ingest_web_file,
)
from app.tools.ingest_web_pages import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = ROOT / "tests/fixtures"
MANIFEST = FIXTURE_DIRECTORY / "web_pages_v1.json"
ARTICLE_HTML = (FIXTURE_DIRECTORY / "web_page_article.html").read_text(encoding="utf-8")
BLOCKED_HTML = (FIXTURE_DIRECTORY / "web_page_blocked.html").read_text(encoding="utf-8")
EMPTY_HTML = (FIXTURE_DIRECTORY / "web_page_empty.html").read_text(encoding="utf-8")


def _client(
    body: str = ARTICLE_HTML,
    *,
    status_code: int = 200,
    content_type: str = "text/html; charset=utf-8",
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        response_headers = {"content-type": content_type, **(headers or {})}
        return httpx.Response(
            status_code,
            text=body,
            headers=response_headers,
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _raw_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_web_ingestion_extracts_semantic_content_and_provenance(tmp_path: Path):
    output = tmp_path / "web-extraction.json"
    with _client() as client:
        extraction = ingest_web_file(MANIFEST, output, client=client)

    page = extraction.pages[0]
    assert str(page.source_url) == "https://example.org/research/article?a=1&b=2"
    assert str(page.requested_url) == "https://example.org/research/article?a=1&b=2"
    assert page.title == "Responsible AI companions for older adults"
    assert page.publisher == "Example Research Institute"
    assert page.retrieved_on.isoformat() == "2026-09-02"
    assert page.http_status == 200
    assert page.content_type == "text/html"
    assert len(page.response_sha256) == len(page.content_sha256) == 64
    extracted_text = " ".join(block.text for block in page.blocks)
    assert "design safeguards" in extracted_text
    assert "Navigation content" not in extracted_text
    assert "Footer content" not in extracted_text
    assert "window.secret" not in extracted_text
    WebExtractionBatch.model_validate_json(output.read_text(encoding="utf-8"))


def test_repeated_web_ingestion_is_byte_identical(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    with _client() as client:
        ingest_web_file(MANIFEST, first, client=client)
    with _client() as client:
        ingest_web_file(MANIFEST, second, client=client)

    assert first.read_bytes() == second.read_bytes()


def test_page_input_order_does_not_change_output(tmp_path: Path):
    raw = _raw_manifest()
    raw["pages"].append(
        {
            "key": "second-article",
            "retrieved_on": "2026-09-02",
            "url": "https://example.org/research/second",
        }
    )
    first_manifest = tmp_path / "first-manifest.json"
    first_manifest.write_text(json.dumps(raw), encoding="utf-8")
    raw["pages"].reverse()
    second_manifest = tmp_path / "second-manifest.json"
    second_manifest.write_text(json.dumps(raw), encoding="utf-8")
    first_output = tmp_path / "first-output.json"
    second_output = tmp_path / "second-output.json"

    with _client() as client:
        ingest_web_file(first_manifest, first_output, client=client)
    with _client() as client:
        ingest_web_file(second_manifest, second_output, client=client)

    assert first_output.read_bytes() == second_output.read_bytes()


def test_disallowed_host_fails_before_fetch(tmp_path: Path):
    raw = _raw_manifest()
    raw["pages"][0]["url"] = "https://not-allowed.example/article"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, text=ARTICLE_HTML, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValidationError, match="not explicitly allowed"):
            ingest_web_file(manifest, tmp_path / "output.json", client=client)
    assert requests == 0


def test_redirect_to_disallowed_host_is_rejected(tmp_path: Path):
    with _client(status_code=302, headers={"location": "https://blocked.example/article"}) as client:
        with pytest.raises(WebExtractionError, match="not explicitly allowed"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


@pytest.mark.parametrize("status_code", [401, 403, 429])
def test_blocked_http_status_is_detected(tmp_path: Path, status_code: int):
    with _client(status_code=status_code) as client:
        with pytest.raises(WebExtractionError, match=f"blocked with HTTP {status_code}"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


def test_challenge_body_is_detected(tmp_path: Path):
    with _client(BLOCKED_HTML) as client:
        with pytest.raises(WebExtractionError, match="blocked or challenge-gated"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


def test_empty_extraction_is_detected(tmp_path: Path):
    with _client(EMPTY_HTML) as client:
        with pytest.raises(WebExtractionError, match="empty or too short"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


def test_non_html_response_is_rejected(tmp_path: Path):
    with _client("not a PDF", content_type="application/pdf") as client:
        with pytest.raises(WebExtractionError, match="unsupported web content type"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


def test_oversized_response_is_rejected(tmp_path: Path):
    oversized = "<html><head><title>Large page</title></head><body><p>" + (
        "evidence " * (MAX_RESPONSE_BYTES // 8)
    ) + "</p></body></html>"
    with _client(oversized) as client:
        with pytest.raises(WebExtractionError, match="response exceeds"):
            ingest_web_file(MANIFEST, tmp_path / "output.json", client=client)


def test_failure_does_not_overwrite_existing_output(tmp_path: Path):
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")
    with _client(EMPTY_HTML) as client:
        with pytest.raises(WebExtractionError):
            ingest_web_file(MANIFEST, output, client=client)
    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_web_ingestion_refuses_direct_active_corpus_write():
    with _client() as client:
        with pytest.raises(ValueError, match="refuses direct writes"):
            ingest_web_file(MANIFEST, ROOT / "data/evidence.json", client=client)


def test_cli_writes_valid_staged_extraction(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    output = tmp_path / "cli-output.json"
    with _client() as client:
        result = main(
            ["--input", str(MANIFEST), "--output", str(output)],
            client=client,
        )

    assert result == 0
    assert "Wrote 1 validated web page(s)" in capsys.readouterr().out
    WebExtractionBatch.model_validate_json(output.read_text(encoding="utf-8"))


def test_localhost_and_ip_allowlist_entries_are_rejected(tmp_path: Path):
    for host in ("localhost", "127.0.0.1", "::1"):
        raw = _raw_manifest()
        raw["allowed_hosts"] = [host]
        manifest = tmp_path / f"manifest-{host.replace(':', '-')}.json"
        manifest.write_text(json.dumps(raw), encoding="utf-8")
        with _client() as client:
            with pytest.raises(ValidationError):
                ingest_web_file(manifest, tmp_path / "output.json", client=client)


def test_web_ingestion_does_not_activate_records(production_repository, tmp_path: Path):
    with _client() as client:
        ingest_web_file(MANIFEST, tmp_path / "staged.json", client=client)
    assert len(production_repository.list_all()) == 6
