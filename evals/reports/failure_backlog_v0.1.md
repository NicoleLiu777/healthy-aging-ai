# Evaluation failure backlog v0.1

| Ticket | Status | Failure class | Cases | Required action | Acceptance test |
|---|---:|---|---|---|---|
| EVAL-FAIL-01 | ✅ Resolved | Implementation bug | 016, 017, 019, 020, 021 | Prevent generic demographic/effectiveness words from establishing relevance. | Same five frozen cases retrieve nothing and abstain; supported cases do not regress. |
| EVAL-FAIL-02 | ⬜ Open | Expected implementation limitation | 013–015 | Add a documented deterministic bilingual vocabulary or another bounded multilingual strategy. | All three frozen Chinese cases retrieve their expected records; unrelated Chinese aging question remains empty. |
| EVAL-FAIL-03 | ⬜ Open | Expected implementation limitation | 007–009 | Represent explicit source-role intent without letting context/design/map sources influence effectiveness conclusions. | Each frozen role-specific case retrieves its expected record and returns an insufficient-evidence brief. |

No Day 4 failure requires expanding the corpus. Questions on nutrition, falls, medication dosing, or vague interventions are negative controls, not invitations to turn the prototype into a general health system.
