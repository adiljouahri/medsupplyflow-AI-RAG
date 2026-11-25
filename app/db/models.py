from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str] = mapped_column(String(60), default="demo-region")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    sterile_type: Mapped[str] = mapped_column(String(40), default="sterile")
    unit_of_measure: Mapped[str] = mapped_column(String(30), nullable=False)
    package_qty: Mapped[int] = mapped_column(Integer, default=1)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="needs_review")
    clinic_code: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("clinics.clinic_code"),
        default="demo-clinic-a",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("clinic_code", "sku", name="uq_products_clinic_sku"),
    )

    requests: Mapped[list["ClientRequest"]] = relationship(
        "ClientRequest", back_populates="product"
    )
    clinic: Mapped["Clinic"] = relationship("Clinic")


class ClientRequest(Base):
    __tablename__ = "client_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    clinic_name: Mapped[str] = mapped_column(String(100), nullable=False)
    clinic_code: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("clinics.clinic_code"),
        default="demo-clinic-a",
        nullable=False,
    )
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    requested_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped[Product | None] = relationship(
        "Product", back_populates="requests"
    )
    clinic: Mapped["Clinic"] = relationship("Clinic")


class IngestionAuditLog(Base):
    __tablename__ = "ingestion_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_code: Mapped[str] = mapped_column(String(40), default="demo-clinic-a")
    source_label: Mapped[str] = mapped_column(String(200), default="legacy-catalog")
    raw_row: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(40), default="rejected")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MultiVectorDocument(Base):
    __tablename__ = "multi_vector_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_code: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("clinics.clinic_code"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )
    source_label: Mapped[str] = mapped_column(String(200), default="legacy-catalog")
    document_label: Mapped[str] = mapped_column(String(200), nullable=False)
    document_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_vectors: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisualPage(Base):
    __tablename__ = "visual_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_code: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("clinics.clinic_code"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )
    source_label: Mapped[str] = mapped_column(String(200), default="visual-catalog")
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_vectors: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
