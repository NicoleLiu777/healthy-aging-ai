# Phase B build, review, activate, and rollback

Status: engineering workflow implemented; expanded corpus and production activation pending.
Baseline: `488e398c77cf6a073a1e8b085eeee122eaf4f777`, six legacy records.
The default `EVIDENCE_PATH` still points to `data/evidence.json`.

## Build a candidate

Run from the repository root in an environment installed from `requirements.txt`.
The paths below are **operator-created reviewed inputs**, not files that this delivery
claims already exist. Do not use `tests/fixtures` or test reviewer identities as source approval.

```bash
python -m app.tools.ingest_structured_sources --input staging/reviewed-sources.json --output staging/corpus-v1.json
python -m app.tools.deduplicate_evidence_corpus --input staging/corpus-v1.json --output staging/dedup.json
python -m app.tools.validate_evidence_candidate --input staging/dedup.json --output staging/validation.json
python -m app.tools.build_corpus_manifest --dedup staging/dedup.json --validation staging/validation.json --version 1.0.0 --output staging/manifest.json
python -m app.tools.build_runtime_release --dedup staging/dedup.json --validation staging/validation.json --manifest staging/manifest.json --mappings staging/reviewed-runtime-mappings.json --output staging/release.json
```

1. Start with the [source register](source-review-register.md). Assess scope, overlap,
   claims, provenance and licences; each theme needs at least ten accepted sources.
2. Use B-04/B-05 to extract accessible sources. Keep failures visible. A downloaded
   article or search result is not a reviewed evidence record.
3. Complete named source review before creating `reviewed-sources.json`. B-03 generates
   stable IDs. Context/design/map claims must remain ineligible for effectiveness.
4. Inspect all B-07 issues. Use the documented recovery/discard command when appropriate.
   Retain original quarantine and recovery artifacts. Rebuild the corrected, reviewed
   source batch through B-03/B-06/B-07 before freezing a manifest; a recovery artifact
   cannot be substituted for a validation bundle.
5. Complete a `ReviewedRuntimeMappingV1` for every accepted source. Its
   `source_record_sha256` must match the canonical JSON digest produced by
   `app.ingestion.manifest.digest`. See `app/ingestion/runtime.py` and its exported schema.
   Required values must be provided explicitly; unknown comparator/sample values may be
   explicit null with a referenced review note. Outcome directions require eligible
   outcome claims; a narrative count does not become an outcome effect.
6. Preserve existing six legacy runtime IDs if they remain in the candidate. Frozen
   v0.1 evaluation expectations still use these IDs; do not edit the gold set to hide failures.

## What the new files guarantee

| Component | Guarantee | Limit |
|---|---|---|
| Manifest | Record/content hashes, all theme/role counts including zeros, configuration versions, report identity, quarantine count, predecessor hash | Empty accepted corpora can be audited, but cannot build a runtime release |
| Validation replay | Manifest and runtime loading recompute B-07 output from retained B-06 input | Hashes are integrity checks, not proof that an article or reviewer is authentic |
| Runtime mapping | Required fields, exact source hash, source-role invariants, explicit pilot metrics and references | Human review must verify meaning and suitability of each mapping |
| Runtime release | Full v1 records, mappings and provenance retained alongside validated legacy projections | Existing `/api/evidence` keeps the legacy response contract; full v1 lives in release artifact |
| Synthesis | Narrative counts, traceable role-specific claims, concrete clarification/refusal text | Model-free lexical matching is bounded; it is not comprehensive adversarial detection |

Changing source content invalidates its mapping. Changing release bytes, application/evaluation
code or coverage suite invalidates matching release approval. The supplied dates are explicit
input dates; no wall-clock timestamp is injected into deterministic ingestion/manifest output.

## Coverage and comparison

Build a `CoverageSuite` containing all three themes and context, design, evidence-map,
unrelated and adversarial categories. Supported cases must specify expected runtime IDs
and claim IDs. Use clinically distinct outcomes and include the nine original human-review
questions. No complete production coverage suite is supplied because new claims are not yet
approved; do not manufacture expected answers before the candidate is curated.

```bash
python -m evals.evaluate_release --release staging/release.json --baseline data/evidence.json --gold evals/questions_v0.1.json --coverage staging/coverage.json --output staging/comparison.json
```

This first run writes results and exits 1 with blockers until sign-off is provided. It checks
the unchanged gold set against both corpora using the same code, reports regressions, evaluates
claim-level coverage, and ties the result to release, code, gold-set and coverage hashes.
Changing the gold file after approval requires fresh review even if the report appears favorable.

Re-run the nine-case blinded review against the candidate; preserve the new raw responses and
reviewer decisions. Do not reuse Day 7 scores for changed outputs. All nine dispositions must
be `accept` after necessary edits and reruns. Create `ReleaseApproval` with the exact hashes
from the report, reviewer/date, release approval and verified rollback code/corpus identifiers.
This is an audit attestation, not a cryptographic identity service. Then run:

```bash
python -m evals.evaluate_release --release staging/release.json --baseline data/evidence.json --gold evals/questions_v0.1.json --coverage staging/coverage.json --approval staging/release-approval.json --output staging/comparison.json
```

Exit 0 and `ready_for_release=true` are required. Do not override failing gates by editing
tests, thresholds, records' source roles, reviewer names or report booleans.

## Activation

1. Retain the exact prior code commit and evidence file, including SHA-256. Verify the
   rollback commit is available in Git and that the saved corpus matches the approval.
2. Create a reviewed PR containing the approved release, manifest, source review artifacts,
   coverage suite, comparison report and this runbook. Check CI on the exact head.
3. Store the release at a version-specific immutable path, for example
   `data/releases/1.0.0/release.json`. Keep the legacy `data/evidence.json` as rollback data.
4. Merge the approved PR and set Render's `EVIDENCE_PATH` to the absolute path of that
   release in the deployed checkout. Restart/redeploy the application; repository objects
   cache data and require restart. Do not partially overwrite an in-use JSON file.
5. Verify `/health`, exact evidence ID set and count, each theme, context/design/map claims,
   an unrelated refusal and an adversarial refusal. Compare responses with the local approved
   release outputs. Inspect startup/load errors and hosting logs. Record deployment ID and time.
6. Mark activation complete only after these live checks succeed. The readiness report itself
   never changes files, environment variables or deployments.

## Rollback

If loading, citations, role boundaries or expected answers regress, redeploy the retained
previous code commit **and** reset `EVIDENCE_PATH` to that revision's saved corpus. Restart
the service and verify health, exact six legacy IDs and supported/context/unrelated cases
using the saved baseline responses. Keep the rejected release and reports for correction.
For a merged change, use a revert PR rather than rewriting main history.

## Add, update, remove and failures

- Add: register and review the source, then rebuild the full candidate and release.
- Update: retain its source identity when appropriate, replace claims/locators only after
  review, regenerate hashes/mapping, and rerun coverage and comparison.
- Remove: document the reason, remove from reviewed inputs, rebuild, and inspect lost coverage.
- Increase corpus version on each release; pass `--previous` to B-08 for a predecessor chain.
- Validation/schema failures: inspect machine-readable paths and quarantine reasons; retain
  prior output. Staged writers validate fully before atomic replacement.
- Source access failures: retain the failure record and seek a permitted authoritative
  source. Do not store a challenge page as article text or call it verified.
- All quarantined: a manifest may record zero accepted sources; release building must fail.

## Outstanding acceptance work

The 30-source register is discovery material, not 30 reviewed records. Nicole reviewed eight
draft records on 2026-09-06. The revised batch accepted four at the source-validation layer and
quarantined four; none of the four effectiveness records is decision eligible until evidence
strength is assigned. B-09 human source curation, B-10/B-11 evaluation on the approved corpus,
renewed human answer review, and a hash-bound B-12 approval remain release conditions.
