import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.structured import (
    StructuredIngestionBatch,
    ingest_structured_file,
    render_corpus,
    transform_structured_batch,
)
from app.models.evidence_v1 import EvidenceCorpusV1


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/structured_sources_v1.json"


def _raw_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_repeated_ingestion_is_byte_identical(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    ingest_structured_file(FIXTURE, first)
    ingest_structured_file(FIXTURE, second)

    assert first.read_bytes() == second.read_bytes()
    EvidenceCorpusV1.model_validate_json(first.read_text(encoding="utf-8"))


def test_input_order_does_not_change_normalized_output():
    raw = _raw_fixture()
    original = StructuredIngestionBatch.model_validate(raw)
    raw["sources"].reverse()
    for source in raw["sources"]:
        source["references"].reverse()
        source["claims"].reverse()
        source["limitations"].reverse()
        source["implementation_implications"].reverse()
    reordered = StructuredIngestionBatch.model_validate(raw)

    assert render_corpus(transform_structured_batch(original)) == render_corpus(
        transform_structured_batch(reordered)
    )


def test_doi_format_changes_do_not_change_record_identity():
    raw = _raw_fixture()
    original = transform_structured_batch(StructuredIngestionBatch.model_validate(raw))
    raw["sources"][0]["doi"] = "doi:10.3390/healthcare13172253"
    reformatted = transform_structured_batch(StructuredIngestionBatch.model_validate(raw))

    original_dino = next(record for record in original.records if record.doi)
    reformatted_dino = next(record for record in reformatted.records if record.doi)
    assert original_dino.record_id == reformatted_dino.record_id
    assert original_dino.doi == reformatted_dino.doi == "10.3390/healthcare13172253"


def test_generated_ids_are_stable_unique_and_linked():
    corpus = transform_structured_batch(
        StructuredIngestionBatch.model_validate(_raw_fixture())
    )

    assert len({record.record_id for record in corpus.records}) == 2
    for record in corpus.records:
        reference_ids = {reference.reference_id for reference in record.references}
        assert all(reference.chunk_id.startswith("chunk-") for reference in record.references)
        assert all(claim.claim_id.startswith("claim-") for claim in record.claims)
        assert all(set(claim.reference_ids) <= reference_ids for claim in record.claims)


def test_invalid_reference_does_not_overwrite_existing_output(tmp_path: Path):
    raw = _raw_fixture()
    raw["sources"][0]["claims"][0]["reference_keys"] = ["missing"]
    invalid_input = tmp_path / "invalid.json"
    invalid_input.write_text(json.dumps(raw), encoding="utf-8")
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")

    with pytest.raises(ValidationError, match="unknown structured reference keys"):
        ingest_structured_file(invalid_input, output)

    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_duplicate_sources_fail_on_stable_record_id_collision():
    raw = _raw_fixture()
    raw["sources"].append(raw["sources"][0])

    with pytest.raises(ValidationError, match="record_id values must be unique"):
        transform_structured_batch(StructuredIngestionBatch.model_validate(raw))


def test_ingestion_refuses_direct_active_corpus_write():
    with pytest.raises(ValueError, match="refuses direct writes"):
        ingest_structured_file(FIXTURE, ROOT / "data/evidence.json")


def test_cli_writes_valid_staged_output(tmp_path: Path):
    output = tmp_path / "staged-corpus.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tools.ingest_structured_sources",
            "--input",
            str(FIXTURE),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Wrote 2 validated record(s)" in result.stdout
    corpus = EvidenceCorpusV1.model_validate_json(output.read_text(encoding="utf-8"))
    assert len(corpus.records) == 2


def test_structured_ingestion_does_not_activate_fixture_records(
    production_repository,
):
    active_records = production_repository.list_all()

    assert len(active_records) == 6
    assert all(not record.id.startswith("evidence-") for record in active_records)

