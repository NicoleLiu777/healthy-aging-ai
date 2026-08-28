# Day 6 source-role intent comparison v0.1

**Date:** 2026-08-28  
**Frozen dataset:** `questions_v0.1.json`, 24 cases  
**Frozen corpus:** `six-record-seed-2026-08-28`, 6 records  
**Before:** deployed Day 5 baseline `01271f7`  
**After:** `candidate-source-role-intent-v1`  
**Only retrieval change:** When a question contains exactly one documented source-role phrase and no effectiveness intent, filter candidates to that source role.

## Same-set result

| Metric | Day 5 | Day 6 | Change |
|---|---:|---:|---:|
| Retrieval hit@5 | 100.0% | 100.0% | 0.0 pp |
| Citation validity | 100.0% | 100.0% | 0.0 pp |
| Abstention correctness | 86.4% | 100.0% | +13.6 pp |
| JSON/schema validity | 100.0% | 100.0% | 0.0 pp |
| Complete case pass rate | 87.5% | 100.0% | +12.5 pp |

These measurements apply only to the frozen 24-case set and six-record corpus. They are not general retrieval, clinical, or production-quality claims.

## What changed

`eval-007`–`eval-009` now retrieve only their requested context, design, or evidence-map source and return an insufficient-evidence brief. The implementation is deterministic and activates only for explicit phrases listed in the Day 6 contract.

Conflict guards leave retrieval unchanged when a question requests more than one source role or includes effectiveness/outcome language. Positive, conflict, and supported-effectiveness regression tests were added. All previously passing frozen cases remained passing.

## Residual risk and next gate

All machine-checkable failures in the frozen set are resolved. Human blinded usefulness scoring remains pending, and the corpus still contains only six records. The 24/24 result must not be treated as clinical validation or evidence of broad-domain coverage.

The next gate is human review of the frozen outputs and a documented decision about the next Phase B theme. Corpus expansion or model integration should require a separate contract and baseline.
