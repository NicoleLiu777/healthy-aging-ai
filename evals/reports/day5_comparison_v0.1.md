# Day 5 multilingual comparison v0.1

**Date:** 2026-08-28  
**Frozen dataset:** `questions_v0.1.json`, 24 cases  
**Frozen corpus:** `six-record-seed-2026-08-28`, 6 records  
**Before:** deployed Day 4 baseline `a61a14b`  
**After:** `candidate-bounded-chinese-aliases-v1`  
**Only retrieval change:** Expand eight explicitly documented Chinese domain phrases into English lexical tokens already present in the corpus.

## Same-set result

| Metric | Day 4 | Day 5 | Change |
|---|---:|---:|---:|
| Retrieval hit@5 | 86.4% | 100.0% | +13.6 pp |
| Citation validity | 100.0% | 100.0% | 0.0 pp |
| Abstention correctness | 72.7% | 86.4% | +13.7 pp |
| JSON/schema validity | 100.0% | 100.0% | 0.0 pp |
| Complete case pass rate | 75.0% | 87.5% | +12.5 pp |

These measurements apply only to the frozen 24-case set and six-record corpus. They are not general multilingual, clinical, or production-quality claims.

## What changed

`eval-013`–`eval-015` now retrieve `marziali-2024`, `li-2023`, and `dino-2025` respectively. The implementation uses no translation service, embeddings, external model, paid call, or corpus change. It does not map generic demographic phrases such as 老人 or 老年人.

Three additional negative tests confirm that Chinese questions about diet, medication, and fall prevention still retrieve nothing. All previously passing frozen cases remained passing.

## Residual failure and next gate

Only `eval-007`–`eval-009` remain: explicit context/design/evidence-map intent still retrieves topical decision-eligible sources, causing the deterministic brief not to abstain. This is `EVAL-FAIL-03` and was not modified on Day 5.

The next engineering gate is a source-role intent contract and same-set test plan. No corpus expansion or model integration should begin as a shortcut around that boundary.
