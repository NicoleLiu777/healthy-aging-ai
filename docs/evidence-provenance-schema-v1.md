# Evidence and provenance schema v1

**Status:** Frozen for Phase B implementation  
**Version:** `1.0.0`  
**Approved themes:** 3  
**Active production corpus migration:** Not started

## Purpose

Schema v1 defines the contract that ingestion must satisfy before a source can enter the active corpus. It separates source metadata, source role, traceable claims, limitations, implementation implications, and decision eligibility so a citation can support a useful answer without being promoted into the wrong kind of evidence.

The current six-record `data/evidence.json` remains the production corpus. The two v1 records under `data/examples/` are validation examples only and are not loaded by the API.

## Required record layers

| Layer | Required contents | Why it exists |
|---|---|---|
| Identity | Schema version, stable record ID, title, authors, DOI | Stable rebuilds and deduplication |
| Theme | One primary and zero or more secondary themes | Coverage reporting across exactly three approved themes |
| Evidence role | Evidence type, source role, record eligibility, strength | Prevent policy/design/map sources from becoming effectiveness proof |
| Provenance | URL, publisher, publication date precision, retrieval/verification dates, verification URLs | Audit and refresh history |
| Access and reuse | Access status/note, license status/note, optional content hash | Avoid silent full-text storage or unsupported reuse |
| References | Stable reference and chunk IDs plus page/section/table/abstract locator | Claim-level traceability |
| Claims | Stable ID, type, paraphrased text, source role, direction, population, outcomes, counts, reference IDs | Preserve findings needed for synthesis |
| Limitations | Traceable statements linked to references | Prevent unqualified conclusions |
| Implementation | Traceable implementation statements | Support bounded pilot decisions without inventing effectiveness |

## Exactly three themes

1. `ai_conversational_agents_mental_health`
2. `older_adult_digital_social_connection`
3. `responsible_ai_companion_design`

Adding or renaming a theme requires schema versioning and a written product decision. It is not a data-only edit to v1.

## Claim types and roles

| Claim type | Typical source role | May be decision eligible? |
|---|---|---:|
| `outcome` | effectiveness | Yes |
| `evidence_summary` | effectiveness | Yes, when direction is explicit |
| `evidence_gap` | evidence_map | No |
| `policy_framing` | context | No |
| `design_principle` | design | No |
| `implementation_requirement` | any matching record role | No |

Only `outcome` and `evidence_summary` claims from an effectiveness record may be decision eligible. Context, design, and evidence-map claims remain answerable and citable, but they cannot determine intervention effectiveness.

## Invariants

- Extra fields are rejected at every schema layer.
- Record, reference, claim, and statement IDs are unique in their scope.
- Every claim, limitation, and implementation implication links to a declared reference ID.
- Every reference records a stable chunk ID and a source locator.
- All claim roles match their record's source role.
- Record eligibility exactly matches the presence of eligible claims.
- Eligible records require an effectiveness role and non-null evidence strength.
- Non-eligible records require null evidence strength.
- Verified sources require a verification date and at least one verification URL.
- Primary and secondary themes cannot duplicate each other.
- Full publication dates are preferred, but `YYYY` and `YYYY-MM` are valid when the source supplies only partial precision.
- Claims are paraphrases; long copied passages are not required by this schema.

## Day 7 findings mapped to v1

| Human-review ticket | Schema response |
|---|---|
| `HREV-01` evidence-map answer had no gap content | `evidence_gap` claims must preserve traceable gap statements and references. |
| `HREV-02` broad question lacked clarification | Not a schema concern; remains a response/UX contract ticket. |
| `HREV-03` 13/15 positive studies were omitted | `evidence_summary` stores study count, qualified direction, narrative finding, and references. The validated Dino example demonstrates it. |
| `HREV-04` adversarial refusal lacked specific explanation | Not a schema concern; remains a response-policy ticket. |
| `HREV-05` design and policy details were absent | `design_principle` and `policy_framing` claims store role-specific, traceable content without effectiveness eligibility. |

## Machine-readable artifacts

- Typed contract: `app/models/evidence_v1.py`
- JSON Schema: `schemas/evidence_corpus_v1.schema.json`
- Validated examples: `data/examples/evidence_records_v1.json`
- Schema exporter: `app/tools/export_evidence_schema.py`

Regenerate the JSON Schema after a deliberate model change:

```bash
PYTHONPATH=. python -m app.tools.export_evidence_schema \
  --output schemas/evidence_corpus_v1.schema.json
```

## Change control

- Patch documentation corrections that do not alter validation may remain v1.0.0.
- Backward-compatible optional fields require a minor version and migration note.
- Required-field, enum, eligibility, ID, or role-rule changes require a major version.
- Never silently rewrite the active corpus to satisfy a new schema.
- Corpus activation requires a separate migration, validation/quarantine report, unchanged-set evaluation, and rollback plan.

## B-02 exit decision

This document, the typed model, exported JSON Schema, validated examples, and invariant tests complete the schema-definition gate. They do not complete ingestion, deduplication, quarantine, corpus versioning, source curation, or runtime migration.

