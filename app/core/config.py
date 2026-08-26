from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "evidence.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SUVANÉ Research RAG"
    app_version: str = "0.2.0"
    cors_origins: str = "http://localhost:5173"
    evidence_path: Path = DEFAULT_EVIDENCE_PATH
    openai_api_key: str = ""
    openai_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
