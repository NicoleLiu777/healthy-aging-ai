from fastapi import Depends

from app.core.config import Settings, get_settings
from app.repositories.evidence_repository import EvidenceRepository


def get_evidence_repository(
    settings: Settings = Depends(get_settings),
) -> EvidenceRepository:
    return EvidenceRepository(settings.evidence_path)


def clear_dependency_caches() -> None:
    get_settings.cache_clear()
