import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.deduplication import (
    DeduplicationConfigV1,
    DeduplicationResultV1,
    deduplicate_corpus,
    deduplicate_corpus_file,
    render_result,
)
from app.ingestion.structured import StructuredIngestionBatch, transform_structured_batch
from app.models.evidence_v1 import EvidenceCorpusV1, EvidenceRecordV1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIXTURE = ROOT / "tests/fixtures/structured_sources_v1.json"


def _source_records() -> list[EvidenceRecordV1]:
    batch = StructuredIngestionBatch.model_validate_json(
        SOURCE_FIXTURE.read_text(encoding="utf-8")
    )
    return transform_structured_batch(batch).records


def _doi_record() -> EvidenceRecordV1:
    return next(record for record in _source_records() if record.doi)


def _no_doi_record() -> EvidenceRecordV1:
    return next(record for record in _source_records() if not record.doi)


def _record(
    base: EvidenceRecordV1,
    token: str,
    *,
    title: str | None = None,
    author: str | None = None,
    year: str | None = None,
    doi: str | None | object = ...,
    source_url: str | None = None,
    content_sha256: str | None | object = ...,
) -> EvidenceRecordV1:
    raw = base.model_dump(mode="json")
    raw["record_id"] = f"evidence-{token}"
    if title is not None:
        raw["title"] = title
    if author is not None:
        raw["authors"][0] = author
    if doi is not ...:
        raw["doi"] = doi
    if source_url is not None:
        raw["provenance"]["source_url"] = source_url
    if year is not None:
        raw["provenance"]["publication_date"] = year
    if content_sha256 is not ...:
        raw["provenance"]["content_sha256"] = content_sha256
    return EvidenceRecordV1.model_validate(raw)


def _corpus(*records: EvidenceRecordV1) -> EvidenceCorpusV1:
    return EvidenceCorpusV1(
        schema_version="1.0.0",
        corpus_id="corpus-deduplication-test",
        generated_on="2026-09-03",
        records=list(records),
    )


def test_exact_doi_duplicates_do_not_inflate_output():
    base = _doi_record()
    duplicate = _record(
        base,
        "doi-copy",
        source_url="https://example.org/a-distinct-page",
    )

    result = deduplicate_corpus(_corpus(base, duplicate))

    assert result.input_record_count == 2
    assert result.output_record_count == 1
    assert result.removed_duplicate_count == 1
    assert result.entities[0].match_rules == ["exact_doi", "exact_bibliographic"]
    assert result.entities[0].review_required is True


def test_exact_url_content_hash_and_bibliographic_rules():
    base = _no_doi_record()
    shared_hash = "a" * 64
    url_copy = _record(base, "url-copy", title="Different title", author="Different")
    hash_left = _record(
        base,
        "hash-left",
        title="Hash left",
        author="Left",
        source_url="https://example.org/hash-left",
        content_sha256=shared_hash,
    )
    hash_right = _record(
        base,
        "hash-right",
        title="Hash right",
        author="Right",
        source_url="https://example.org/hash-right",
        content_sha256=shared_hash,
    )
    bibliographic = _record(
        base,
        "bibliographic-copy",
        source_url="https://example.org/bibliographic-copy",
    )

    url_result = deduplicate_corpus(_corpus(base, url_copy))
    hash_result = deduplicate_corpus(_corpus(hash_left, hash_right))
    bibliographic_result = deduplicate_corpus(_corpus(base, bibliographic))

    assert url_result.entities[0].match_rules == ["exact_source_url"]
    assert hash_result.entities[0].match_rules == ["exact_content_sha256"]
    assert bibliographic_result.entities[0].match_rules == ["exact_bibliographic"]


def test_configured_near_title_rule_and_false_positive_guards():
    base = _doi_record()
    near = _record(
        base,
        "near-copy",
        title=(
            "Remote Virtual Interactive Agents for Older Adults: Exploring Its "
            "Science via Network Analysis & Systematic Review"
        ),
        doi=None,
        source_url="https://example.org/near-copy",
    )
    different_year = _record(near, "different-year", year="2024")
    different_author = _record(near, "different-author", author="Another Author")

    near_result = deduplicate_corpus(_corpus(base, near))
    year_result = deduplicate_corpus(_corpus(base, different_year))
    author_result = deduplicate_corpus(_corpus(base, different_author))

    assert near_result.output_record_count == 1
    assert near_result.entities[0].match_rules == ["near_title"]
    assert year_result.output_record_count == 2
    assert author_result.output_record_count == 2


def test_near_title_can_be_disabled_and_threshold_is_validated():
    base = _doi_record()
    near = _record(
        base,
        "near-disabled",
        title=base.title.replace(" and ", " & "),
        doi=None,
        source_url="https://example.org/near-disabled",
    )

    result = deduplicate_corpus(
        _corpus(base, near), DeduplicationConfigV1(enable_near_title=False)
    )

    assert result.output_record_count == 2
    with pytest.raises(ValidationError):
        DeduplicationConfigV1(title_similarity_threshold=0.5)


def test_transitive_groups_and_output_are_input_order_independent():
    base = _no_doi_record()
    first = _record(
        base,
        "transitive-a",
        title="First unique title",
        author="First",
        content_sha256="1" * 64,
    )
    bridge = _record(
        base,
        "transitive-b",
        title="Bridge unique title",
        author="Bridge",
        content_sha256="2" * 64,
    )
    last = _record(
        base,
        "transitive-c",
        title="Last unique title",
        author="Last",
        source_url="https://example.org/transitive-c",
        content_sha256="2" * 64,
    )

    forward = deduplicate_corpus(_corpus(first, bridge, last))
    reverse = deduplicate_corpus(_corpus(last, bridge, first))

    assert forward.output_record_count == 1
    assert forward.entities[0].match_rules == [
        "exact_content_sha256",
        "exact_source_url",
    ]
    assert render_result(forward) == render_result(reverse)


def test_canonical_selection_prefers_doi_and_entity_id_is_stable():
    base = _doi_record()
    without_doi = _record(
        base,
        "canonical-no-doi",
        doi=None,
        source_url="https://example.org/no-doi",
    )
    with_doi = _record(base, "canonical-doi", source_url="https://example.org/doi")

    result = deduplicate_corpus(_corpus(without_doi, with_doi))
    repeated = deduplicate_corpus(_corpus(with_doi, without_doi))

    assert result.entities[0].canonical_record_id == "evidence-canonical-doi"
    assert result.entities[0].entity_id == repeated.entities[0].entity_id


def test_singletons_receive_entity_mapping_without_review():
    result = deduplicate_corpus(_corpus(*_source_records()))

    assert result.output_record_count == 2
    assert all(not entity.review_required for entity in result.entities)
    assert all(entity.match_rules == [] for entity in result.entities)


def test_repeated_file_command_is_byte_identical(tmp_path: Path):
    corpus = _corpus(*_source_records())
    input_path = tmp_path / "input.json"
    input_path.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    deduplicate_corpus_file(input_path, first)
    deduplicate_corpus_file(input_path, second)

    assert first.read_bytes() == second.read_bytes()
    DeduplicationResultV1.model_validate_json(first.read_text(encoding="utf-8"))


def test_invalid_config_does_not_overwrite_existing_output(tmp_path: Path):
    corpus = _corpus(*_source_records())
    input_path = tmp_path / "input.json"
    input_path.write_text(corpus.model_dump_json(), encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text('{"title_similarity_threshold": 0.2}', encoding="utf-8")
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")

    with pytest.raises(ValidationError):
        deduplicate_corpus_file(input_path, output, config_path)

    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_command_refuses_direct_active_corpus_write(tmp_path: Path):
    input_path = tmp_path / "input.json"
    input_path.write_text(_corpus(*_source_records()).model_dump_json(), encoding="utf-8")

    with pytest.raises(ValueError, match="refuses direct writes"):
        deduplicate_corpus_file(input_path, ROOT / "data/evidence.json")


def test_cli_writes_auditable_staged_result(tmp_path: Path):
    base = _doi_record()
    duplicate = _record(base, "cli-copy", source_url="https://example.org/cli-copy")
    input_path = tmp_path / "input.json"
    input_path.write_text(_corpus(base, duplicate).model_dump_json(), encoding="utf-8")
    output = tmp_path / "deduplicated.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tools.deduplicate_evidence_corpus",
            "--input",
            str(input_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "removed 1 duplicate candidate(s)" in completed.stdout
    result = DeduplicationResultV1.model_validate_json(output.read_text(encoding="utf-8"))
    assert result.entities[0].review_required is True


def test_deduplication_does_not_activate_fixture_records(production_repository):
    active_records = production_repository.list_all()

    assert len(active_records) == 6
    assert all(not record.id.startswith("evidence-") for record in active_records)
