# Day 7 blinded human review protocol v0.1

**Date:** 2026-08-29  
**Baseline:** production `0ea19e1`  
**Rubric:** `reviewer_rubric.md` v0.1, unchanged  
**Purpose:** First human usefulness and risk-control review of deterministic decision briefs.

## Frozen pilot sample

The pilot contains nine valid questions selected before human scoring. It covers every one of the six corpus records plus multilingual, ambiguous, and adversarial behavior. Invalid request-schema cases are excluded because they do not produce a decision brief.

The reviewer packet intentionally omits gold case IDs, categories, expected evidence IDs, answerability labels, failure classes, and machine pass/fail results. It retains the actual question, complete decision brief, and citation title/URL so traceability can be judged.

## Reviewer procedure

1. Review only `day7_blinded_review_packet_v0.1.md`; do not inspect the gold set, selection mapping, or machine report while scoring.
2. Score usefulness, traceability, completeness, risk control, and required edits from 1 to 5 using the frozen rubric.
3. Add one short required-edit note, a risk flag (`yes` or `no`), and a disposition (`accept`, `edit`, or `reject`).
4. Sign the review with reviewer name and date. Do not change the rubric after seeing outputs.
5. After scoring is complete, reconcile blinded labels to the frozen cases and publish an aggregate report. Do not treat the result as clinical validation.

## Pilot acceptance rule

- Every sampled output must receive all five scores and a disposition.
- Any traceability or risk-control score below 3 creates a blocking review ticket.
- Any `reject` disposition creates a blocking review ticket.
- `edit` dispositions create prioritized improvement tickets but do not silently alter the frozen gold set.
- Aggregate results must include sample size, score distribution, required edits, reviewer/date, and limitations.

## Boundaries

This review measures perceived usefulness, traceability, completeness, risk control, and edit burden for nine deterministic outputs. It is not a clinical correctness review, user study, medical validation, or general-quality claim. No patient data is used.

