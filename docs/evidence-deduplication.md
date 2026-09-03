# Deterministic evidence deduplication (B-06)

This command groups duplicate records in a validated, staged `EvidenceCorpusV1` and
emits an auditable result containing a canonical candidate corpus. It does not merge
claims, delete the source artifact, or activate records in production.

## Run the command

```bash
python -m app.tools.deduplicate_evidence_corpus \
  --input staging/evidence-corpus-v1.json \
  --output staging/evidence-deduplication-v1.json
```

An optional strict JSON configuration can set the near-title controls:

```json
{
  "config_version": "1.0.0",
  "enable_near_title": true,
  "title_similarity_threshold": 0.94,
  "minimum_normalized_title_length": 20,
  "require_same_publication_year": true,
  "require_same_first_author": true
}
```

Pass it with `--config path/to/deduplication-config.json`. The effective configuration
is copied into the result, making each run reproducible and reviewable.

## Match rules

Exact rules are always enabled. A pair is grouped when it shares at least one of:

1. normalized DOI;
2. non-null provenance `content_sha256`;
3. canonical source URL (lowercase scheme/host, collapsed path slashes, sorted query,
   no fragment); or
4. normalized title + publication year + normalized first author.

The configured near-duplicate rule uses deterministic `SequenceMatcher` similarity on
Unicode-normalized, case-folded titles. By default, both publication year and first
author must match, the shorter normalized title must contain at least 20 characters,
and similarity must be at least `0.94`. The rule can be disabled. Its allowed threshold
range is `0.80` through `1.00`.

Pair matches are joined transitively with a deterministic union-find pass, so source
ordering does not change entity membership or output bytes.

## Canonical records and stable entities

Each entity receives `entity-<16 hex>` from its strongest stable identity: DOI, then
content hash, then bibliographic signature, then record IDs. Every input record,
including a singleton, appears in exactly one entity.

The retained canonical record is selected deterministically, preferring:

1. a DOI;
2. verified provenance;
3. permitted licensing;
4. open access;
5. richer claim/reference traceability; and
6. lexical `record_id` as the final tie-breaker.

Only canonical records appear in `deduplicated_corpus`, so duplicates cannot inflate
later retrieval results. The original staged input remains unchanged. Multi-record
entities have `review_required: true`; no claims or traceable statements are silently
merged, because a duplicate representation may contain unique evidence that B-07 must
review.

## Safety and failure behavior

- Input and output are validated with strict Pydantic contracts.
- Output is canonical JSON and repeated unchanged runs are byte-identical.
- Writes are atomic; validation failures preserve an existing output file.
- Direct output to `data/evidence.json` is rejected.
- This stage performs no network request, OCR, claim inference, embedding, model call,
  database write, or production activation.
