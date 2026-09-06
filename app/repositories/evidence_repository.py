import json
from pathlib import Path

from app.models.evidence import EvidenceRecord, EvidenceStrength


class EvidenceRepository:
    def __init__(self, evidence_path: Path) -> None:
        self._evidence_path = evidence_path
        self._records: list[EvidenceRecord] | None = None

    def _load_records(self) -> list[EvidenceRecord]:
        if self._records is None:
            raw = self._evidence_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                from app.ingestion.runtime import RuntimeReleaseV1, load_release
                self._records = load_release(RuntimeReleaseV1.model_validate(data))
            else:
                self._records = [EvidenceRecord.model_validate(item) for item in data]
        return self._records

    def list_all(self) -> list[EvidenceRecord]:
        return list(self._load_records())

    def filter(
        self,
        query: str | None = None,
        strength: EvidenceStrength | None = None,
    ) -> list[EvidenceRecord]:
        records = self._load_records()

        if strength is not None:
            records = [
                record
                for record in records
                if record.evidence_strength == strength
            ]

        if query:
            normalized_query = query.lower().strip()
            records = [
                record
                for record in records
                if self._matches_query(record, normalized_query)
            ]

        return records

    @staticmethod
    def _matches_query(record: EvidenceRecord, query: str) -> bool:
        searchable = " ".join(
            [
                record.title,
                record.population,
                record.study_type,
                record.intervention,
                record.comparison or "",
                " ".join(record.topic),
                " ".join(record.outcomes_improved),
                " ".join(record.outcomes_not_improved),
                " ".join(record.limitations),
                " ".join(record.implementation_implications),
                record.evidence_strength_rationale,
                " ".join(claim.text for claim in getattr(getattr(record, "evidence_v1", None), "claims", [])),
            ]
        ).lower()
        return query in searchable
