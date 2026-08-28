# Deterministic evaluation comparison v0.1

**Date:** 2026-08-28  
**Frozen dataset:** `questions_v0.1.json`, 24 cases  
**Frozen corpus:** `six-record-seed-2026-08-28`, 6 records  
**Before:** backend production baseline `6c2d74e`  
**After:** `generic-term-filter-v1` candidate  
**Only retrieval change:** Treat generic demographic/effectiveness terms (`older`, `adult(s)`, `intervention(s)`, `effective(ness)`) as non-discriminative stop words.

## Same-set result

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Retrieval hit@5 | 63.6% | 86.4% | +22.8 pp |
| Citation validity | 100.0% | 100.0% | 0.0 pp |
| Abstention correctness | 50.0% | 72.7% | +22.7 pp |
| JSON/schema validity | 100.0% | 100.0% | 0.0 pp |
| Complete case pass rate | 54.2% | 75.0% | +20.8 pp |

These numbers describe only the frozen 24-case set. They are not claims about clinical correctness, general RAG quality, or production performance.

## What changed

Five previously failing cases now pass: nutrition, fall-prevention wearables, medication dosing, an underspecified pilot question, and an undefined “this intervention” question. Before the change, generic population/effectiveness words supplied the two distinct keyword matches needed to retrieve unrelated records. After the change, those words cannot establish relevance by themselves.

No previously passing case regressed. Citation validity and response schema validity remained unchanged.

## Residual failures

- `eval-007`–`eval-009`: source-role intent is not represented in scoring, so context/design/evidence-map questions also retrieve decision-eligible topical records and fail the expected abstention rule.
- `eval-013`–`eval-015`: Chinese paraphrases do not match the English-only corpus vocabulary under deterministic lexical retrieval.

## Failure classification

- **Resolved implementation bug:** generic demographic/effectiveness tokens caused false-positive retrieval.
- **Open implementation limitations:** multilingual lexical mapping and source-role intent.
- **Corpus gaps:** none were added to the six-record corpus. Nutrition, falls, medication dosing, and other unrelated cases are deliberate noncoverage and must abstain, not trigger corpus expansion during Day 4.

## Gate

The deterministic baseline and same-set comparison are reproducible. Before corpus expansion, Nicole should review the gold-set expectations and qualitative rubric. The next implementation ticket may address exactly one residual class without editing v0.1 cases; any gold-set change requires v0.2 and a written changelog.
