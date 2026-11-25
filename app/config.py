import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: Literal["development", "staging", "production", "test"] = "development"
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

    # LangSmith Tracing & Observability
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="medsupplyflow-ai", alias="LANGCHAIN_PROJECT")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production":
            insecure_key = self.internal_api_key in {"demo-internal-api-key", "", None}
            insecure_db = "demo-password" in self.database_url
            if insecure_key:
                raise ValueError("Production environment cannot use default or empty internal_api_key")
            if insecure_db:
                raise ValueError("Production environment cannot use demo database password in database_url")
        return self

    def apply_langsmith_tracing(self) -> None:
        """Propagate LangSmith tracing flags to process environment for LangGraph/LangChain/LiteLLM."""
        if self.langchain_tracing_v2:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_project
            os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_endpoint
            if self.langchain_api_key:
                os.environ["LANGCHAIN_API_KEY"] = self.langchain_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

