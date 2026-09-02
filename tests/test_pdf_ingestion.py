import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter

from app.ingestion.pdf import (
    MAX_PDF_BYTES,
    PDFExtractionBatch,
    PDFIngestionError,
    ingest_pdf_file,
)
from app.tools.ingest_pdf_documents import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = ROOT / "tests/fixtures"
MANIFEST = FIXTURE_DIRECTORY / "pdf_documents_v1.json"
PDF_FIXTURE_B64 = FIXTURE_DIRECTORY / "mixed_text_image.pdf.b64"


def _raw_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _materialize_fixture(directory: Path) -> tuple[Path, Path]:
    pdf_path = directory / "mixed_text_image.pdf"
    encoded = PDF_FIXTURE_B64.read_text(encoding="ascii")
    pdf_path.write_bytes(base64.b64decode(encoded))
    manifest_path = directory / "pdf_documents_v1.json"
    manifest_path.write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    return manifest_path, pdf_path


def _write_manifest(directory: Path, document: dict) -> Path:
    raw = _raw_manifest()
    raw["documents"] = [document]
    path = directory / "manifest.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_pdf_ingestion_preserves_page_provenance_and_flags_image_page(
    tmp_path: Path,
):
    manifest, _ = _materialize_fixture(tmp_path)
    output = tmp_path / "pdf-extraction.json"
    extraction = ingest_pdf_file(manifest, output)

    document = extraction.documents[0]
    assert str(document.source_url) == (
        "https://example.org/research/mixed-fixture.pdf?a=1&b=2"
    )
    assert document.status == "partial_manual_review"
    assert document.review_reasons == ["page_requires_review"]
    assert document.page_count == 2
    assert document.title == "SUVANE PDF ingestion fixture"
    assert len(document.file_sha256 or "") == 64
    assert document.pages[0].page_number == 1
    assert document.pages[0].locator == "page 1"
    assert document.pages[0].status == "extracted"
    assert "implementation safeguards" in (document.pages[0].text or "")
    assert document.pages[1].page_number == 2
    assert document.pages[1].locator == "page 2"
    assert document.pages[1].status == "manual_review"
    assert document.pages[1].review_reason == "image_only_page"
    assert document.pages[1].image_count == 1
    PDFExtractionBatch.model_validate_json(output.read_text(encoding="utf-8"))


def test_repeated_pdf_ingestion_is_byte_identical(tmp_path: Path):
    manifest, _ = _materialize_fixture(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    ingest_pdf_file(manifest, first)
    ingest_pdf_file(manifest, second)
    assert first.read_bytes() == second.read_bytes()


def test_pdf_manifest_order_does_not_change_output(tmp_path: Path):
    raw = _raw_manifest()
    raw["documents"].append(
        {
            "expected_sha256": None,
            "file": "missing.pdf",
            "key": "missing-document",
            "retrieved_on": "2026-09-02",
            "source_url": "https://example.org/research/missing.pdf",
        }
    )
    first_manifest = tmp_path / "first-manifest.json"
    first_manifest.write_text(json.dumps(raw), encoding="utf-8")
    raw["documents"].reverse()
    second_manifest = tmp_path / "second-manifest.json"
    second_manifest.write_text(json.dumps(raw), encoding="utf-8")
    _materialize_fixture(tmp_path)
    first_output = tmp_path / "first-output.json"
    second_output = tmp_path / "second-output.json"

    ingest_pdf_file(first_manifest, first_output)
    ingest_pdf_file(second_manifest, second_output)
    assert first_output.read_bytes() == second_output.read_bytes()


def test_image_only_document_is_flagged_for_manual_review(tmp_path: Path):
    _, pdf_fixture = _materialize_fixture(tmp_path)
    reader = PdfReader(pdf_fixture)
    writer = PdfWriter()
    writer.add_page(reader.pages[1])
    image_only = tmp_path / "image-only.pdf"
    with image_only.open("wb") as handle:
        writer.write(handle)
    document = _raw_manifest()["documents"][0]
    document["file"] = image_only.name
    document["expected_sha256"] = None
    document["source_url"] = "https://example.org/research/image-only.pdf"
    manifest = _write_manifest(tmp_path, document)

    extraction = ingest_pdf_file(manifest, tmp_path / "output.json")
    result = extraction.documents[0]
    assert result.status == "manual_review"
    assert result.review_reasons == ["image_only_document"]
    assert result.pages[0].review_reason == "image_only_page"


def test_invalid_pdf_is_retained_as_manual_review(tmp_path: Path):
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"not a PDF")
    document = _raw_manifest()["documents"][0]
    document["file"] = invalid.name
    document["expected_sha256"] = None
    document["source_url"] = "https://example.org/research/invalid.pdf"
    manifest = _write_manifest(tmp_path, document)

    result = ingest_pdf_file(manifest, tmp_path / "output.json").documents[0]
    assert result.status == "manual_review"
    assert result.review_reasons == ["invalid_pdf"]
    assert result.page_count == 0
    assert len(result.file_sha256 or "") == 64


def test_encrypted_pdf_is_retained_as_manual_review(tmp_path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("fixture-password")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as handle:
        writer.write(handle)
    document = _raw_manifest()["documents"][0]
    document["file"] = encrypted.name
    document["expected_sha256"] = None
    document["source_url"] = "https://example.org/research/encrypted.pdf"
    manifest = _write_manifest(tmp_path, document)

    result = ingest_pdf_file(manifest, tmp_path / "output.json").documents[0]
    assert result.status == "manual_review"
    assert result.review_reasons == ["encrypted_pdf"]


def test_missing_pdf_is_retained_as_manual_review(tmp_path: Path):
    document = _raw_manifest()["documents"][0]
    document["file"] = "missing.pdf"
    document["expected_sha256"] = None
    document["source_url"] = "https://example.org/research/missing.pdf"
    manifest = _write_manifest(tmp_path, document)

    result = ingest_pdf_file(manifest, tmp_path / "output.json").documents[0]
    assert result.status == "manual_review"
    assert result.review_reasons == ["file_not_found"]
    assert result.file_sha256 is None


def test_hash_mismatch_does_not_overwrite_existing_output(tmp_path: Path):
    _materialize_fixture(tmp_path)
    document = _raw_manifest()["documents"][0]
    document["expected_sha256"] = "0" * 64
    manifest = _write_manifest(tmp_path, document)
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")

    with pytest.raises(PDFIngestionError, match="SHA-256"):
        ingest_pdf_file(manifest, output)
    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_manifest_cannot_escape_its_directory(tmp_path: Path):
    document = _raw_manifest()["documents"][0]
    document["file"] = "../outside.pdf"
    manifest = _write_manifest(tmp_path, document)
    with pytest.raises(PDFIngestionError, match="escapes"):
        ingest_pdf_file(manifest, tmp_path / "output.json")


def test_non_pdf_manifest_path_is_rejected(tmp_path: Path):
    document = _raw_manifest()["documents"][0]
    document["file"] = "source.txt"
    manifest = _write_manifest(tmp_path, document)
    with pytest.raises(PDFIngestionError, match="relative .pdf"):
        ingest_pdf_file(manifest, tmp_path / "output.json")


def test_oversized_pdf_is_rejected(tmp_path: Path):
    oversized = tmp_path / "oversized.pdf"
    with oversized.open("wb") as handle:
        handle.truncate(MAX_PDF_BYTES + 1)
    document = _raw_manifest()["documents"][0]
    document["file"] = oversized.name
    document["expected_sha256"] = None
    document["source_url"] = "https://example.org/research/oversized.pdf"
    manifest = _write_manifest(tmp_path, document)
    with pytest.raises(PDFIngestionError, match="PDF exceeds"):
        ingest_pdf_file(manifest, tmp_path / "output.json")


def test_duplicate_source_urls_are_rejected(tmp_path: Path):
    raw = _raw_manifest()
    duplicate = dict(raw["documents"][0])
    duplicate["key"] = "duplicate"
    raw["documents"].append(duplicate)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError, match="source URLs must be unique"):
        ingest_pdf_file(manifest, tmp_path / "output.json")


def test_non_https_source_url_is_rejected(tmp_path: Path):
    document = _raw_manifest()["documents"][0]
    document["source_url"] = "http://example.org/research/source.pdf"
    manifest = _write_manifest(tmp_path, document)
    with pytest.raises(ValidationError, match="must use HTTPS"):
        ingest_pdf_file(manifest, tmp_path / "output.json")


def test_pdf_ingestion_refuses_direct_active_corpus_write(tmp_path: Path):
    manifest, _ = _materialize_fixture(tmp_path)
    with pytest.raises(ValueError, match="refuses direct writes"):
        ingest_pdf_file(manifest, ROOT / "data/evidence.json")


def test_cli_writes_staged_extraction_and_review_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    manifest, _ = _materialize_fixture(tmp_path)
    output = tmp_path / "cli-output.json"
    assert main(["--input", str(manifest), "--output", str(output)]) == 0
    assert "1 require manual review" in capsys.readouterr().out
    PDFExtractionBatch.model_validate_json(output.read_text(encoding="utf-8"))


def test_pdf_ingestion_does_not_activate_records(production_repository, tmp_path: Path):
    manifest, _ = _materialize_fixture(tmp_path)
    ingest_pdf_file(manifest, tmp_path / "staged.json")
    assert len(production_repository.list_all()) == 6
