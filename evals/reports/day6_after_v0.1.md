# Day 6 after explicit source-role intent — deterministic evaluation v0.1

- Run: `2026-08-28T21:09:33.867964+00:00`
- Code: `candidate-source-role-intent-v1`
- Corpus: `six-record-seed-2026-08-28` (6 records)
- Dataset: `v0.1` (24 cases)
- Retrieval: deterministic keyword/topic match, top_k=5

## Results

| Metric | Result |
|---|---:|
| Retrieval hit@5 | 100.0% |
| Citation validity | 100.0% |
| Abstention correctness | 100.0% |
| JSON/schema validity | 100.0% |
| Complete case pass rate | 100.0% |

## Case-level failures

| Case | Category | Retrieved IDs | Failed checks | Classification |
|---|---|---|---|---|
| — | — | — | None | — |

## Limitations

- Metrics describe only this frozen 24-case set and six-record corpus.
- No human usefulness review or clinical validation was performed.
- No paid model, embeddings, or semantic retrieval were used.
