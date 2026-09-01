# Structured-source ingestion v1

**Ticket:** B-03  
**Mode:** Offline and deterministic  
**Active corpus writes:** Prohibited

## Purpose

The structured-source ingestion command converts a reviewed JSON batch into a normalized `EvidenceCorpusV1`. It validates the B-02 contract, derives stable content-based IDs, canonicalizes ordering and URLs, and writes the output atomically to a staging path.

It does not fetch the web, parse PDFs, infer claims, translate text, call a model, or activate records in `data/evidence.json`.

## Run

```bash
PYTHONPATH=. python -m app.tools.ingest_structured_sources \
  --input tests/fixtures/structured_sources_v1.json \
  --output build/staged/evidence-corpus-v1.json
```

Run the same command again with unchanged input. The output bytes must be identical.

## Input contract

The batch fixes `input_version`, `corpus_id`, and `generated_on`. A timestamp is never generated at runtime because that would make the same input produce different output.

Each source supplies reviewed metadata and human-authored, traceable claims. References use short local keys only inside the input file. Claims, limitations, and implementation implications link to those keys. The ingestion transformer replaces them with stable IDs.

## Stable-ID rules

| ID | Deterministic seed |
|---|---|
| Record | Normalized DOI; canonical source URL when DOI is absent |
| Reference | Record identity + locator type + normalized locator + canonical source URL |
| Chunk | Record identity + reference locator with a chunk namespace |
| Claim | Record identity + normalized claim content + resolved references |
| Limitation/implication | Record identity + normalized statement + resolved references |

Hashes are truncated SHA-256 identifiers. DOI prefixes and casing are normalized. URL scheme/host casing, duplicate slashes, query ordering, and fragments are canonicalized. Records, references, claims, limitations, implications, themes, populations, outcomes, and reference links are sorted where their order has no semantic meaning.

Author order remains unchanged because it is semantically meaningful.

## Determinism and safety guarantees

- Repeated ingestion of unchanged input is byte-identical.
- Reordering sources or unordered record elements does not change output.
- Stable-ID collisions or duplicate sources fail validation.
- Unknown reference keys fail before the destination is touched.
- The output is fully validated as `EvidenceCorpusV1` before writing.
- Writes use a temporary file and atomic replacement.
- Direct output to `data/evidence.json` is rejected.
- Existing production retrieval, synthesis, response schema, and six-record corpus remain unchanged.

## Failure handling

B-03 fails closed: invalid input exits non-zero and produces no replacement output. It does not yet create a rejected-record store. A structured validation/quarantine report belongs to B-07 and must not be silently added here.

## Rollback

The command is offline and non-activating. Rollback is removal or reversion of the B-03 ingestion module, CLI, fixtures, tests, and documentation. Staged outputs can be deleted without changing production. Never roll back by overwriting `data/evidence.json`.

## Exit evidence

- Implementation: `app/ingestion/structured.py`
- CLI: `app/tools/ingest_structured_sources.py`
- Multi-role fixture: `tests/fixtures/structured_sources_v1.json`
- Tests: `tests/test_structured_ingestion.py`

B-03 completion does not complete web ingestion, PDF ingestion, deduplication, quarantine, corpus manifests, curation, coverage evaluation, or production activation.

