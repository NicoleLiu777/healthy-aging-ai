# After generic-term retrieval filter — deterministic evaluation v0.1

- Run: `2026-08-28T05:41:56.172068+00:00`
- Code: `candidate-generic-term-filter-v1`
- Corpus: `six-record-seed-2026-08-28` (6 records)
- Dataset: `v0.1` (24 cases)
- Retrieval: deterministic keyword/topic match, top_k=5

## Results

| Metric | Result |
|---|---:|
| Retrieval hit@5 | 86.4% |
| Citation validity | 100.0% |
| Abstention correctness | 72.7% |
| JSON/schema validity | 100.0% |
| Complete case pass rate | 75.0% |

## Case-level failures

| Case | Category | Retrieved IDs | Failed checks | Classification |
|---|---|---|---|---|
| eval-007 | context_only | who-2025, marziali-2024, welch-2023-egm | abstention | none |
| eval-008 | context_only | loveys-2019, marziali-2024, li-2023 | abstention | none |
| eval-009 | context_only | welch-2023-egm, who-2025, marziali-2024 | abstention | none |
| eval-013 | multilingual | — | retrieval, abstention | expected_limitation |
| eval-014 | multilingual | — | retrieval, abstention | expected_limitation |
| eval-015 | multilingual | — | retrieval, abstention | expected_limitation |

## Limitations

- Metrics describe only this frozen 24-case set and six-record corpus.
- No human usefulness review or clinical validation was performed.
- No paid model, embeddings, or semantic retrieval were used.
