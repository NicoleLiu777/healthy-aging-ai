# Evidence validation and recoverable quarantine (B-07)

B-07 converts a B-06 deduplication result into one deterministic validation bundle.
The bundle contains a record-level validation report, the accepted staged candidate,
and a recoverable quarantine store. It never writes to the active production corpus.

## Validate a deduplicated candidate

```bash
python -m app.tools.validate_evidence_candidate \
  --input staging/evidence-deduplication-v1.json \
  --output staging/evidence-validation-v1.json
```

The optional `--config` file is strict JSON. Defaults are:

```json
{
  "config_version": "1.0.0",
  "require_verified_provenance": true,
  "quarantine_duplicate_entities": true,
  "quarantine_unknown_access": true,
  "quarantine_unknown_license": true
}
```

The effective configuration is embedded in the report. Production activation must
use the defaults unless a reviewed decision explicitly documents an exception.

## What is quarantined

| Reason code | Meaning | Recovery action |
|---|---|---|
| `schema_validation_error` | The record fails the frozen `EvidenceRecordV1` contract. | Correct every reported field path, then submit the complete record for recovery. |
| `missing_entity_mapping` | The record is not a canonical member of the B-06 entity map. | Rebuild B-06 with the corrected record; do not invent an entity mapping. |
| `duplicate_review_required` | B-06 found multiple representations of the entity. | Review possible unique claims, then explicitly approve the canonical record or replace it. |
| `provenance_not_verified` | Provenance is still marked `needs_review`. | Verify against authoritative sources and add the required audit evidence. |
| `access_status_unknown` | Access conditions have not been resolved. | Record the reviewed access status and explanatory note. |
| `license_status_unknown` | Permitted/restricted use has not been resolved. | Record the reviewed license status and explanatory note. |
| `record_id_collision` | A correction would duplicate an already accepted record ID. | Rebuild stable identity upstream or discard the duplicate after review. |

Restricted licensing, subscription access, and abstract-only access are not silently
treated as permission to reproduce source text. They can remain as reviewed metadata
states, while downstream curation must respect their recorded constraints.

## Validation bundle

The single atomically written JSON artifact contains:

- `report`: stable report ID, input/accepted/quarantined counts, issue counts, and a
  result for every input record;
- `accepted_candidate`: only records that passed schema, provenance, access, license,
  entity, and duplicate-review gates; and
- `quarantine_store`: stable quarantine IDs, complete raw record payloads, entity IDs
  when available, field paths, messages, and open status.

An empty accepted candidate is valid. This prevents an all-invalid batch from failing
before its rejection evidence can be saved. Every input record appears in exactly one
of the accepted or quarantined partitions.

## Recover or discard quarantined records

Create a reviewed corrections file:

```json
{
  "recovery_version": "1.0.0",
  "corrections": [
    {
      "quarantine_id": "quarantine-00000000000000000000",
      "disposition": "replace",
      "corrected_record": {},
      "duplicate_review_approved": false,
      "reviewed_by": "Reviewer name",
      "reviewed_on": "2026-09-04",
      "resolution_note": "What was checked and changed."
    }
  ]
}
```

Then run:

```bash
python -m app.tools.recover_quarantined_evidence \
  --bundle staging/evidence-validation-v1.json \
  --corrections staging/quarantine-corrections-v1.json \
  --output staging/evidence-recovery-v1.json
```

`replace` revalidates the entire corrected record under the original validation
configuration. Duplicate entities remain blocked unless
`duplicate_review_approved=true`. Failed corrections retain the same quarantine ID
and updated payload for another review cycle. `discard` requires no corrected record
and creates a dated reviewer decision instead of silently dropping the source.

The recovery result contains the original accepted records plus recovered records,
remaining quarantine entries, and every reviewer decision. Corrections cannot target
unknown quarantine IDs or collide with accepted record IDs.

## Safety and rollback

- Input structure, configuration, reports, corrections, and recovery results are
  strict Pydantic contracts.
- Record-level schema failures are captured rather than skipped.
- Outputs use canonical JSON; unchanged runs are byte-identical.
- Validation occurs before atomic file replacement, so failures preserve existing
  staged output.
- Both commands reject direct output to `data/evidence.json`.
- The source B-06 artifact and quarantine payloads remain unchanged and can be rerun.
- No network fetch, OCR, inference, embedding, model call, database write, or
  production activation occurs.

B-08 may create a versioned manifest only from the accepted/recovered candidate and
must record any remaining quarantine count. Quarantined records never enter that
manifest's active candidate set.
