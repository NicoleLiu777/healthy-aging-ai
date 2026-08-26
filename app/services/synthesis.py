from app.models.decision import Citation, DecisionBrief, PilotRecommendation
from app.models.evidence import EvidenceRecord, EvidenceStrength

STRENGTH_RANK: dict[EvidenceStrength, int] = {
    "early": 0,
    "limited": 1,
    "moderate": 2,
    "strong": 3,
}

PILOT_BY_STRENGTH: dict[EvidenceStrength, PilotRecommendation] = {
    "strong": "pilot",
    "moderate": "pilot_with_safeguards",
    "limited": "pilot_with_safeguards",
    "early": "do_not_pilot",
}


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _decision_eligible_records(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    return [record for record in records if record.decision_eligible]


def _aggregate_evidence_strength(records: list[EvidenceRecord]) -> EvidenceStrength:
    """Conservative Phase 1 interim rule applied only to decision-eligible records.

    Example: strong + moderate + early => early.

    Context, design, and evidence-map sources must not influence this aggregate.
    This will be replaced by a formal evidence-grading framework in a later phase.
    """
    return min(records, key=lambda record: STRENGTH_RANK[record.evidence_strength]).evidence_strength


def _build_pilot_metrics(records: list[EvidenceRecord]) -> list[str]:
    return _dedupe_preserve_order(
        [
            *(
                outcome
                for record in records
                for outcome in record.outcomes_improved
            ),
            *(
                outcome
                for record in records
                for outcome in record.outcomes_not_improved
            ),
        ]
    )


def _build_conclusion(
    question: str,
    decision_records: list[EvidenceRecord],
    strength: EvidenceStrength,
    retrieved_count: int,
) -> str:
    populations = _dedupe_preserve_order([record.population for record in decision_records])
    improved = _dedupe_preserve_order(
        outcome for record in decision_records for outcome in record.outcomes_improved
    )
    population_text = "; ".join(populations)
    outcome_text = "; ".join(improved) if improved else "no clearly improved outcomes documented"

    return (
        f"Based on {len(decision_records)} decision-eligible record(s) "
        f"({retrieved_count} total retrieved) with {strength} overall strength, "
        f"the available evidence for the question '{question}' indicates studied populations "
        f"including {population_text}. Documented improved outcomes include: {outcome_text}. "
        "This is a deterministic Phase 1 draft synthesis derived only from stored evidence records."
    )


def _role_claim(record: EvidenceRecord) -> str:
    role_labels = {
        "context": "Context source for policy and framing",
        "design": "Design source for intervention planning",
        "evidence_map": "Evidence-map source for corpus orientation",
    }
    return role_labels[record.source_role]


def _build_citations(records: list[EvidenceRecord]) -> list[Citation]:
    citations: list[Citation] = []
    for record in records:
        if record.decision_eligible:
            claims = _dedupe_preserve_order(record.outcomes_improved)
            if not claims:
                claims = [f"Study examined: {record.intervention}"]
        else:
            claims = [_role_claim(record)]
        citations.append(
            Citation(
                evidence_id=record.id,
                title=record.title,
                url=record.url,
                supported_claims=claims,
            )
        )
    return citations


def _insufficient_brief(question: str, reason: str) -> DecisionBrief:
    return DecisionBrief(
        question=question,
        conclusion=(
            "Insufficient decision-eligible evidence is available in the current evidence corpus "
            "to produce a grounded decision brief for this question."
        ),
        evidence_strength="insufficient",
        populations_studied=[],
        outcomes_improved=[],
        outcomes_not_improved_or_unclear=[],
        limitations_and_risks=[],
        pilot_recommendation="insufficient_evidence",
        pilot_metrics=[],
        citations=[],
        insufficient_evidence_reason=reason,
    )


def synthesize_decision_brief(
    question: str,
    records: list[EvidenceRecord],
) -> DecisionBrief:
    if not records:
        return _insufficient_brief(
            question,
            (
                "No sufficiently relevant evidence records were retrieved from the stored corpus "
                "using deterministic keyword and topic matching."
            ),
        )

    decision_records = _decision_eligible_records(records)
    if not decision_records:
        return DecisionBrief(
            question=question,
            conclusion=(
                "Insufficient decision-eligible evidence is available in the current evidence corpus "
                "to produce a grounded decision brief for this question."
            ),
            evidence_strength="insufficient",
            populations_studied=[],
            outcomes_improved=[],
            outcomes_not_improved_or_unclear=[],
            limitations_and_risks=[],
            pilot_recommendation="insufficient_evidence",
            pilot_metrics=[],
            citations=_build_citations(records),
            insufficient_evidence_reason=(
                "Retrieved sources did not include decision-eligible effectiveness evidence."
            ),
        )

    strength = _aggregate_evidence_strength(decision_records)
    return DecisionBrief(
        question=question,
        conclusion=_build_conclusion(question, decision_records, strength, len(records)),
        evidence_strength=strength,
        populations_studied=_dedupe_preserve_order(
            record.population for record in decision_records
        ),
        outcomes_improved=_dedupe_preserve_order(
            outcome for record in decision_records for outcome in record.outcomes_improved
        ),
        outcomes_not_improved_or_unclear=_dedupe_preserve_order(
            outcome for record in decision_records for outcome in record.outcomes_not_improved
        ),
        limitations_and_risks=_dedupe_preserve_order(
            limitation for record in decision_records for limitation in record.limitations
        ),
        pilot_recommendation=PILOT_BY_STRENGTH[strength],
        pilot_metrics=_build_pilot_metrics(decision_records),
        citations=_build_citations(records),
        insufficient_evidence_reason=None,
    )
