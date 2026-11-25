import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_secrets_validation_fails_on_demo_key() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            internal_api_key="demo-internal-api-key",
            database_url="postgresql+psycopg://user:prod_secret@db:5432/db",
        )
    assert "internal_api_key" in str(exc.value)


def test_production_secrets_validation_fails_on_demo_db() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            internal_api_key="real-secure-production-key",
            database_url="postgresql+psycopg://medsupply:demo-password@postgres:5432/medsupplyflow",
        )
    assert "demo-password" in str(exc.value)


def test_production_secrets_validation_succeeds_with_strong_creds() -> None:
    settings = Settings(
        environment="production",
        internal_api_key="super-secret-production-key-xyz",
        database_url="postgresql+psycopg://medsupply:secure_pass_123@postgres:5432/medsupplyflow",
    )
    assert settings.environment == "production"
    assert settings.internal_api_key == "super-secret-production-key-xyz"


def test_langsmith_tracing_propagation(monkeypatch) -> None:
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

    settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="lsv2_pt_test_key",
        LANGCHAIN_PROJECT="test-project",
    )
    settings.apply_langsmith_tracing()

    import os
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_API_KEY") == "lsv2_pt_test_key"
    assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"
