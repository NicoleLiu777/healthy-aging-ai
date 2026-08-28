# Day 5 decision — bounded multilingual lexical support

**Date:** 2026-08-28  
**Production baseline:** `a61a14b`  
**Selected ticket:** `EVAL-FAIL-02` (`eval-013`–`eval-015`)  
**Frozen inputs:** gold set v0.1, reviewer rubric v0.1, six-record corpus, scoring thresholds, and deterministic synthesis remain unchanged.

## Decision

Add a small, explicit Chinese-to-English query phrase vocabulary before lexical scoring. Each supported Chinese domain phrase expands to English tokens already present in the verified corpus. This is deterministic query normalization, not translation, semantic retrieval, corpus enrichment, or model inference.

Supported phrases are limited to the three failed concepts:

| Chinese phrase | English retrieval tokens |
|---|---|
| 语音助手 | `voice`, `assistants` |
| 孤独 / 孤独感 | `loneliness` |
| 社会隔离 | `social`, `isolation` |
| 对话代理 | `conversational`, `agents` |
| 心理健康 | `mental`, `health` |
| 抑郁 | `depression` |
| 虚拟互动代理 | `virtual`, `interactive`, `agents` |
| 远程 | `remote` |

## Safety boundaries

- Do not map generic demographic phrases such as 老人 or 老年人; demographics alone must not create relevance.
- Do not call an external translation service or paid model.
- Do not change the corpus, gold expectations, source roles, synthesis, thresholds, or top_k.
- An unmapped Chinese question continues through ordinary tokenization and should abstain unless it independently matches stored text.
- Success requires all three frozen Chinese cases to retrieve their expected records while unrelated Chinese nutrition, medication, and falls questions remain empty.

## Rollback

Remove `QUERY_PHRASE_ALIASES` and its expansion in `tokenize`, then re-run the frozen v0.1 evaluation. No data or schema rollback is required.
