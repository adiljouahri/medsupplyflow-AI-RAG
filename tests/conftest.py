"""Shared fixtures that keep the whole suite offline.

PostgreSQL is replaced by an in-memory SQLite database and the Chroma,
multi-vector, and visual stores are replaced by fakes. CI therefore needs no
services, no Docker daemon, and no API keys.

Heavy modules (``app.main``, ``app.ingestion.normalizer``) are imported inside
the fixtures that need them so the pure unit tests never pay their import cost.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Clinic, Product

DEMO_CLINICS = (
    ("demo-clinic-a", "Demo Clinic A"),
    ("demo-clinic-b", "Demo Clinic B"),
    ("demo-clinic-c", "Demo Clinic C"),
)

PRODUCT_DEFAULTS = {
    "sku": "SC-15",
    "canonical_name": "Sterile Scalpel #15",
    "category": "surgical instrument",
    "sterile_type": "sterile",
    "unit_of_measure": "pcs",
    "package_qty": 10,
    "stock_quantity": 50,
    "notes": "stainless steel",
    "confidence_score": 0.9,
    "status": "approved",
    "clinic_code": "demo-clinic-a",
}


class FakeVectorStore:
    """Stands in for the Chroma HTTP client and records what it was asked to do."""

    def __init__(self, matches: list[dict] | None = None) -> None:
        self.matches = matches or []
        self.indexed: list[int] = []
        self.deleted: list[tuple[int, str]] = []
        self.queries: list[tuple[str, str]] = []

    def index_product(self, product: Product) -> None:
        self.indexed.append(product.id)

    def delete_product_document(self, product_id: int, clinic_code: str) -> None:
        self.deleted.append((product_id, clinic_code))

    def query(
        self,
        query: str,
        limit: int = 5,
        clinic_code: str | None = None,
    ) -> list[dict]:
        self.queries.append((query, clinic_code or ""))
        return list(self.matches)[:limit]


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """In-memory SQLite kept alive across connections by StaticPool."""
    test_engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def seeded_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """A session holding the three synthetic clinics every tenant check relies on."""
    session = session_factory()
    session.add_all(
        Clinic(clinic_code=code, canonical_name=name, region="demo-region")
        for code, name in DEMO_CLINICS
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def product_factory(seeded_session: Session):
    """Create and persist a Product, overriding any default."""

    def _create(**overrides) -> Product:
        values = {**PRODUCT_DEFAULTS, **overrides}
        product = Product(**values)
        seeded_session.add(product)
        seeded_session.commit()
        return product

    return _create


@pytest.fixture()
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    from app.config import get_settings

    return {"X-API-Key": get_settings().internal_api_key}


@pytest.fixture()
def api_client(
    session_factory: sessionmaker[Session],
    fake_vector_store: FakeVectorStore,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator:
    """TestClient wired to SQLite; no Postgres, Chroma, or LLM is contacted."""
    from fastapi.testclient import TestClient

    from app.ingestion import normalizer as normalizer_module
    from app.main import app, get_db

    def _multi_vector_store_unavailable():
        raise RuntimeError("advanced retrieval dependencies are not installed")

    # ingest_rows() opens its own session and vector store, so patch at the source.
    monkeypatch.setattr(normalizer_module, "SessionLocal", session_factory)
    monkeypatch.setattr(normalizer_module, "VectorStore", lambda: fake_vector_store)

    monkeypatch.setattr("app.main.VectorStore", lambda: fake_vector_store)
    monkeypatch.setattr("app.main.get_multi_vector_store", _multi_vector_store_unavailable)
    monkeypatch.setattr(
        "app.main.delete_product_document",
        fake_vector_store.delete_product_document,
    )
    # The lifespan handler seeds PostgreSQL; keep it out of the test path.
    monkeypatch.setattr("app.main.init_db", lambda: None)

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
