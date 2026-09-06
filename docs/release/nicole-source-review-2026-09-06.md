# Nicole source review — 2026-09-06

Nicole reviewed the eight-source packet. Six sources received conditional acceptance with specific edits; WHO and Tess remain quarantined. The exact reviewer decisions are preserved in `evals/reviews/phase_b_source_review_2026-09-06.json`.

| Source | Human decision | Applied result | Remaining gate |
|---|---|---|---|
| He 2023 | Edit then accept | Timing anchors and 8/11/13 bias distribution added to claims; CC BY 4.0 confirmed | Effectiveness strength grading |
| Campbell EGM | Edit then accept | May 2021 cutoff and September 2026 staleness moved into claim text | Source-specific licence |
| WHO 2025 | Quarantine | No claims accepted from overview-only material | Full text, page locators and licence |
| Skjuve 2021 | Edit then accept | Narrow 18-person established-relationship sample moved into claim | Source-specific licence |
| Woebot 2017 | Edit then accept | Commercial affiliation, two-week window, design, population and 17% missing follow-up bound to the claim | Effectiveness strength grading |
| Tess 2018 | Priority quarantine | Repository-wide search found no deleted response example in downstream content; correction and X2AI disclosure retained | Nicole post-correction acceptance decision |
| Wysa 2018 | Edit then accept | Usage-defined groups, 108:21 imbalance and noncausal interpretation placed in the claim | Effectiveness strength grading |
| Youper 2021 | Edit then accept | Youper affiliations and divergent anxiety/depression directions placed in claim; retention limitation retained | Effectiveness strength grading |

The rebuilt batch 3 pipeline accepted four records and quarantined four. “Accepted” here means the source passed provenance/access/licence validation after Nicole's requested edits. The four effectiveness records remain `decision_eligible=false` because Nicole did not assign evidence strength; they cannot yet influence effectiveness conclusions.

Campbell and Skjuve have approved claim wording but remain quarantined because the source-specific licence is unresolved. WHO has both provenance and licence issues. Tess remains unverified after its correction even though the downstream audit found no deleted quote.

Nicole also authorized a future B-12 activation with paired rollback. That authorization is conditional because no exact release version or SHA exists yet. The release evaluator still requires at least ten reviewed sources in each theme, passing coverage and frozen comparison, nine accepted human cases, and an approval object bound to the exact release/code/gold/coverage hashes.
