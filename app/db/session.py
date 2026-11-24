from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..config import get_settings
from .base import Base
from .models import ClientRequest, Clinic, IngestionAuditLog, MultiVectorDocument, Product, VisualPage  # noqa: F401 (load tables)


def make_engine():
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        for code, name in (
            ("demo-clinic-a", "Demo Clinic A"),
            ("demo-clinic-b", "Demo Clinic B"),
            ("demo-clinic-c", "Demo Clinic C"),
        ):
            exists = session.execute(
                select(Clinic).where(Clinic.clinic_code == code)
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    Clinic(
                        clinic_code=code,
                        canonical_name=name,
                        region="demo-region",
                    )
                )
        session.commit()
