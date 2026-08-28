# Deterministic Evaluation Baseline v0.1

This directory freezes the evaluation contract for the six-record SUVANÉ Research corpus before retrieval changes. It evaluates a narrow employment-focused FDE prototype, not a clinical or commercial product.

## Frozen contract

- Gold set: `questions_v0.1.json`; edits require a new dataset version and a written reason.
- Corpus: `data/evidence.json`, six human-verified records.
- Retrieval: deterministic keyword/topic matching, `top_k=5`.
- Synthesis: deterministic `DecisionBrief`; no model or prompt call.
- Inputs contain no real patient data or sensitive personal information.

### Answerability labels

| Label | Expected behavior |
|---|---|
| `answerable` | At least one expected decision-eligible record is retrieved and the brief does not abstain. |
| `context_only` | Expected non-eligible context/design/map records may be cited, but the brief must abstain. |
| `insufficient` | No grounded decision brief is available; the brief must abstain. |
| `invalid` | Request validation must reject the input before retrieval. |

### Metrics

| Metric | Machine-checkable rule |
|---|---|
| Retrieval hit@5 | Every expected evidence ID is present in the top-five retrieved IDs; an empty expectation requires empty retrieval. Invalid inputs are excluded. |
| Citation validity | Every citation ID exists in the corpus, was retrieved, and appears once. |
| Abstention correctness | `answerable` cases return a non-insufficient brief; `context_only` and `insufficient` cases return `insufficient_evidence`. |
| Schema validity | Valid inputs round-trip through `DecisionBrief`; `invalid` inputs are rejected by `AskRequest`. |

These are sample-set measurements, not general quality or clinical-performance claims. A before/after comparison is valid only when the same dataset and corpus are used.

## Run

```bash
PYTHONPATH=. python evals/run_evaluation.py \
  --questions evals/questions_v0.1.json \
  --output-json evals/reports/results.json \
  --output-md evals/reports/results.md \
  --code-version "$(git rev-parse --short HEAD)" \
  --label local
```

The command exits non-zero when any case fails. Reports contain case-level failures so corpus gaps, expected prototype limitations, and implementation bugs can be ticketed separately.
