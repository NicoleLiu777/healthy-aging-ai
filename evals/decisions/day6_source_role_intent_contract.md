# Day 6 decision — explicit source-role intent

**Date:** 2026-08-28  
**Production baseline:** `01271f7`  
**Selected ticket:** `EVAL-FAIL-03` (`eval-007`–`eval-009`)  
**Frozen inputs:** gold set v0.1, reviewer rubric v0.1, six-record corpus, query aliases, scoring thresholds, deterministic synthesis, and top_k remain unchanged.

## Problem

The lexical retriever correctly finds the requested context, design, or evidence-map record, but also retrieves topically related effectiveness records. Deterministic synthesis then produces an effectiveness recommendation even when the user explicitly asked only for policy framing, design principles, or evidence gaps.

## Decision

Detect a source-role intent only when the query contains one of these explicit phrase groups:

| Intended role | Trigger phrases |
|---|---|
| `context` | `policy framing`, `policy context`, `WHO policy` |
| `design` | `design principles`, `design insights`, `interaction design` |
| `evidence_map` | `evidence gap`, `evidence gaps`, `evidence map`, `gap map` |

When exactly one role is detected, lexical scoring is limited to records with that `source_role`. Synthesis remains unchanged: because those records are not decision-eligible, the response must abstain while retaining the contextual citation.

## Conflict guards

- If more than one source role is requested, do not filter.
- If the same query explicitly asks about effectiveness, improvement, outcomes, or whether an intervention works/reduces an outcome, do not filter.
- Ordinary supported questions must retain their prior retrieval behavior.
- A role phrase is not an authorization to change record eligibility or treat context/design/map material as effectiveness evidence.

## Exclusions

- No corpus or gold-set edit.
- No model, classifier, embeddings, reranker, or external service.
- No change to synthesis, thresholds, top_k, evidence eligibility, or response schema.
- No broad inference from isolated words such as `policy`, `design`, `evidence`, or `gap`.

## Acceptance and rollback

All three frozen role-specific cases must retrieve their expected record and abstain. Supported, multilingual, unrelated, ambiguous, adversarial, and malformed cases must not regress. Rollback removes role-intent detection/filtering and re-runs v0.1; no data or schema rollback is required.
