from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://medsupply:demo-password@postgres:5432/medsupplyflow"
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    internal_api_key: str = "demo-internal-api-key"
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_rows: int = Field(default=500, ge=1, le=5000)
    llm_model: str = "openai/gpt-4o-mini"
    llm_api_key: str | None = None
    ollama_base_url: str = "http://host.docker.internal:11434"
    multi_vector_model: str = "lightonai/mLateOn"
    visual_model: str | None = "vidore/colpali-v1.3"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
