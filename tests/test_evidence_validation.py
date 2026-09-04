import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.deduplication import deduplicate_corpus
from app.ingestion.structured import StructuredIngestionBatch, transform_structured_batch
from app.ingestion.validation import (
    CandidateValidationBundleV1,
    QuarantineRecoveryBatchV1,
    RawDeduplicationResultV1,
    QuarantineRecoveryResultV1,
    recover_quarantine,
    recover_quarantine_file,
    render_artifact,
    validate_candidate,
    validate_candidate_file,
)
from app.models.evidence_v1 import EvidenceCorpusV1, EvidenceRecordV1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIXTURE = ROOT / "tests/fixtures/structured_sources_v1.json"


def _records() -> list[EvidenceRecordV1]:
    batch = StructuredIngestionBatch.model_validate_json(
        SOURCE_FIXTURE.read_text(encoding="utf-8")
    )
    records = transform_structured_batch(batch).records
    validated: list[EvidenceRecordV1] = []
    for record in records:
        raw = record.model_dump(mode="json")
        raw["provenance"]["license_status"] = "permitted"
        raw["provenance"]["license_note"] = "Reviewed for staged metadata use."
        validated.append(EvidenceRecordV1.model_validate(raw))
    return validated


def _corpus(*records: EvidenceRecordV1) -> EvidenceCorpusV1:
    return EvidenceCorpusV1(
        schema_version="1.0.0",
        corpus_id="corpus-validation-test",
        generated_on="2026-09-04",
        records=list(records),
    )


def _candidate(*records: EvidenceRecordV1) -> RawDeduplicationResultV1:
    result = deduplicate_corpus(_corpus(*records))
    return RawDeduplicationResultV1.model_validate(
        result.model_dump(mode="json")
    )


def _write_candidate(path: Path, candidate: RawDeduplicationResultV1) -> None:
    path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")


def _correction(
    quarantine_id: str,
    *,
    corrected_record: dict | None,
    disposition: str = "replace",
    duplicate_review_approved: bool = False,
) -> QuarantineRecoveryBatchV1:
    return QuarantineRecoveryBatchV1.model_validate(
        {
            "recovery_version": "1.0.0",
            "corrections": [
                {
                    "quarantine_id": quarantine_id,
                    "disposition": disposition,
                    "corrected_record": corrected_record,
                    "duplicate_review_approved": duplicate_review_approved,
                    "reviewed_by": "Nicole",
                    "reviewed_on": "2026-09-04",
                    "resolution_note": "Reviewed against the authoritative source.",
                }
            ],
        }
    )


def test_valid_records_are_accepted_with_empty_quarantine_store():
    bundle = validate_candidate(_candidate(*_records()))

    assert bundle.report.input_record_count == 2
    assert bundle.report.accepted_record_count == 2
    assert bundle.report.quarantined_record_count == 0
    assert bundle.report.issue_counts == {}
    assert len(bundle.accepted_candidate.records) == 2
    assert bundle.quarantine_store.entries == []


def test_schema_invalid_record_is_quarantined_with_raw_payload_and_path():
    raw = _candidate(*_records()).model_dump(mode="json")
    del raw["deduplicated_corpus"]["records"][0]["provenance"]["publisher"]
    bundle = validate_candidate(RawDeduplicationResultV1.model_validate(raw))

    assert bundle.report.accepted_record_count == 1
    assert bundle.report.quarantined_record_count == 1
    entry = bundle.quarantine_store.entries[0]
    assert entry.raw_record["provenance"].get("publisher") is None
    assert any(issue.code == "schema_validation_error" for issue in entry.issues)
    assert any(issue.path == "provenance.publisher" for issue in entry.issues)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("verification_status", "needs_review", "provenance_not_verified"),
        ("access_status", "unknown", "access_status_unknown"),
        ("license_status", "unknown", "license_status_unknown"),
    ],
)
def test_unresolved_provenance_is_quarantined(field, value, expected_code):
    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"][field] = value
    record = EvidenceRecordV1.model_validate(raw_record)

    bundle = validate_candidate(_candidate(record))

    assert bundle.report.accepted_record_count == 0
    assert bundle.report.quarantined_record_count == 1
    assert expected_code in bundle.report.record_results[0].issue_codes


def test_duplicate_entity_requires_human_review():
    base = _records()[0]
    raw_copy = base.model_dump(mode="json")
    raw_copy["record_id"] = "evidence-duplicate-review-copy"
    duplicate = EvidenceRecordV1.model_validate(raw_copy)

    bundle = validate_candidate(_candidate(base, duplicate))

    assert bundle.report.input_record_count == 1
    assert bundle.report.accepted_record_count == 0
    entry = bundle.quarantine_store.entries[0]
    assert entry.entity_id is not None
    assert [issue.code for issue in entry.issues] == ["duplicate_review_required"]


def test_corrected_record_is_recovered_into_candidate():
    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"]["license_status"] = "unknown"
    bundle = validate_candidate(
        _candidate(EvidenceRecordV1.model_validate(raw_record))
    )
    entry = bundle.quarantine_store.entries[0]
    corrected = dict(entry.raw_record)
    corrected["provenance"] = dict(corrected["provenance"])
    corrected["provenance"]["license_status"] = "permitted"

    result = recover_quarantine(
        bundle,
        _correction(entry.quarantine_id, corrected_record=corrected),
    )

    assert result.decisions[0].disposition == "recovered"
    assert len(result.recovered_candidate.records) == 1
    assert result.remaining_quarantine_store.entries == []


def test_unfixed_record_remains_recoverable_in_quarantine():
    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"]["license_status"] = "unknown"
    bundle = validate_candidate(
        _candidate(EvidenceRecordV1.model_validate(raw_record))
    )
    entry = bundle.quarantine_store.entries[0]

    result = recover_quarantine(
        bundle,
        _correction(entry.quarantine_id, corrected_record=entry.raw_record),
    )

    assert result.decisions[0].disposition == "still_quarantined"
    assert result.decisions[0].issue_codes == ["license_status_unknown"]
    assert result.remaining_quarantine_store.entries[0].quarantine_id == entry.quarantine_id


def test_duplicate_recovery_requires_explicit_review_approval():
    base = _records()[0]
    raw_copy = base.model_dump(mode="json")
    raw_copy["record_id"] = "evidence-duplicate-recovery-copy"
    bundle = validate_candidate(
        _candidate(base, EvidenceRecordV1.model_validate(raw_copy))
    )
    entry = bundle.quarantine_store.entries[0]

    blocked = recover_quarantine(
        bundle,
        _correction(entry.quarantine_id, corrected_record=entry.raw_record),
    )
    approved = recover_quarantine(
        bundle,
        _correction(
            entry.quarantine_id,
            corrected_record=entry.raw_record,
            duplicate_review_approved=True,
        ),
    )

    assert blocked.decisions[0].disposition == "still_quarantined"
    assert approved.decisions[0].disposition == "recovered"


def test_reviewed_record_can_be_discarded_with_audit_decision():
    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"]["access_status"] = "unknown"
    bundle = validate_candidate(
        _candidate(EvidenceRecordV1.model_validate(raw_record))
    )
    entry = bundle.quarantine_store.entries[0]

    result = recover_quarantine(
        bundle,
        _correction(
            entry.quarantine_id,
            corrected_record=None,
            disposition="discard",
        ),
    )

    assert result.decisions[0].disposition == "discarded"
    assert result.recovered_candidate.records == []
    assert result.remaining_quarantine_store.entries == []


def test_unknown_quarantine_id_fails_without_overwriting_output(tmp_path: Path):
    bundle = validate_candidate(_candidate(*_records()))
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(render_artifact(bundle), encoding="utf-8")
    corrections_path = tmp_path / "corrections.json"
    recovery = _correction(
        "quarantine-00000000000000000000",
        corrected_record=_records()[0].model_dump(mode="json"),
    )
    corrections_path.write_text(render_artifact(recovery), encoding="utf-8")
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown quarantine IDs"):
        recover_quarantine_file(bundle_path, corrections_path, output)

    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_validation_file_is_byte_identical_and_strict(tmp_path: Path):
    input_path = tmp_path / "candidate.json"
    _write_candidate(input_path, _candidate(*_records()))
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    validate_candidate_file(input_path, first)
    validate_candidate_file(input_path, second)

    assert first.read_bytes() == second.read_bytes()
    CandidateValidationBundleV1.model_validate_json(first.read_text(encoding="utf-8"))


def test_invalid_config_preserves_existing_output(tmp_path: Path):
    input_path = tmp_path / "candidate.json"
    _write_candidate(input_path, _candidate(*_records()))
    config_path = tmp_path / "config.json"
    config_path.write_text('{"unexpected": true}', encoding="utf-8")
    output = tmp_path / "output.json"
    output.write_text("preserve-me", encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_candidate_file(input_path, output, config_path)

    assert output.read_text(encoding="utf-8") == "preserve-me"


def test_validation_and_recovery_refuse_active_corpus_writes(tmp_path: Path):
    input_path = tmp_path / "candidate.json"
    _write_candidate(input_path, _candidate(*_records()))
    with pytest.raises(ValueError, match="refuses direct writes"):
        validate_candidate_file(input_path, ROOT / "data/evidence.json")

    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"]["license_status"] = "unknown"
    bundle = validate_candidate(
        _candidate(EvidenceRecordV1.model_validate(raw_record))
    )
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(render_artifact(bundle), encoding="utf-8")
    entry = bundle.quarantine_store.entries[0]
    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        render_artifact(_correction(entry.quarantine_id, corrected_record=entry.raw_record)),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="refuses direct writes"):
        recover_quarantine_file(
            bundle_path, corrections_path, ROOT / "data/evidence.json"
        )


def test_validation_cli_writes_report_and_quarantine_store(tmp_path: Path):
    input_path = tmp_path / "candidate.json"
    _write_candidate(input_path, _candidate(*_records()))
    output = tmp_path / "validation.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tools.validate_evidence_candidate",
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
    assert "Accepted 2 record(s); quarantined 0 record(s)" in completed.stdout
    CandidateValidationBundleV1.model_validate_json(output.read_text(encoding="utf-8"))


def test_recovery_cli_writes_revalidated_candidate(tmp_path: Path):
    raw_record = _records()[0].model_dump(mode="json")
    raw_record["provenance"]["license_status"] = "unknown"
    bundle = validate_candidate(
        _candidate(EvidenceRecordV1.model_validate(raw_record))
    )
    entry = bundle.quarantine_store.entries[0]
    corrected = entry.raw_record | {
        "provenance": entry.raw_record["provenance"] | {"license_status": "permitted"}
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(render_artifact(bundle), encoding="utf-8")
    corrections_path = tmp_path / "corrections.json"
    corrections_path.write_text(
        render_artifact(_correction(entry.quarantine_id, corrected_record=corrected)),
        encoding="utf-8",
    )
    output = tmp_path / "recovered.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tools.recover_quarantined_evidence",
            "--bundle",
            str(bundle_path),
            "--corrections",
            str(corrections_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Recovered 1" in completed.stdout
    result = QuarantineRecoveryResultV1.model_validate_json(
        output.read_text(encoding="utf-8")
    )
    assert len(result.recovered_candidate.records) == 1


def test_validation_does_not_activate_candidate_records(production_repository):
    active_records = production_repository.list_all()

    assert len(active_records) == 6
    assert all(not record.id.startswith("evidence-") for record in active_records)
