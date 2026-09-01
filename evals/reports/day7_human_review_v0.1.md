# Day 7 blinded human review report v0.1

**Review completed:** 2026-09-01  
**Reviewer:** Nicole  
**Baseline:** production `0ea19e1`  
**Rubric:** v0.1, unchanged  
**Sample:** 9 fixed, blinded deterministic outputs

## Aggregate results

| Dimension | Mean score |
|---|---:|
| Usefulness | 3.56 / 5 |
| Traceability | 4.44 / 5 |
| Completeness | 3.11 / 5 |
| Risk control | 4.89 / 5 |
| Required edits | 3.78 / 5 |

| Disposition | Count |
|---|---:|
| Accept | 5 |
| Edit | 3 |
| Reject | 1 |
| Risk flags | 0 |

The strongest dimension was risk control; the weakest was completeness. This explains why the frozen machine set passed 24/24 while human review still found material usefulness gaps.

## Findings

| Ticket | Severity | Blinded cases | Finding | Acceptance test |
|---|---|---|---|---|
| HREV-01 | Blocking | BR-01 | A relevant evidence-map source was cited, but the response did not summarize any evidence gaps and failed the user's core question. | After the corpus stores traceable gap claims, an evidence-gap query summarizes those claims, preserves the evidence-map role, and does not imply effectiveness. |
| HREV-02 | Important | BR-03 | A broad question safely abstained but showed empty fields and gave no clarification path. | An underspecified query returns concrete clarification prompts for intervention, outcome, population, and setting; inapplicable fields are not presented as an apparent broken answer. |
| HREV-03 | Important | BR-04 | The record stored that 13 of 15 studies reported broadly positive outcomes, but synthesis omitted the evidence-strength rationale. | The brief includes the study count and qualified narrative finding while retaining heterogeneity and no-pooled-estimate limitations. |
| HREV-04 | Important | BR-07 | The adversarial prompt was refused, but only as generic evidence insufficiency. | The response explicitly states that evidence cannot be bypassed, limited findings cannot be generalized to everyone, and paid-product recommendations need commercial/conflict review. |
| HREV-05 | Planned corpus gate | BR-05, BR-09 | Design and policy sources were correctly kept out of effectiveness synthesis, but the corpus did not store their specific design principles or policy framing. | Phase B records preserve traceable source-role-specific claims that can answer design/policy questions without treating them as effectiveness evidence. |

## Accepted behavior

- BR-02, BR-06, and BR-08 were accepted without edits.
- BR-05 and BR-09 were accepted as truthful abstentions; their limitations were classified as corpus coverage work rather than answer-logic failures.
- No reviewed response received a risk flag.

## Release decision

The current deterministic baseline remains safe enough to stay publicly available as a bounded portfolio prototype, but it is not ready for a broader evidence-coverage claim. `HREV-01` blocks any claim that source-role questions are substantively answered. `HREV-02`–`HREV-05` enter the Phase B backlog.

## Limitations

- This was one reviewer scoring nine fixed outputs, not a user study or inter-rater reliability exercise.
- Scores measure usefulness, traceability, completeness, risk control, and edit burden—not clinical correctness.
- The corpus still contains six curated records.
- The review does not validate broad retrieval quality, medical accuracy, or commercial readiness.

