"""Initial schema with clinics, products, requests, audit, and vector docs.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-27 16:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # clinics
    op.create_table(
        "clinics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("canonical_name", sa.String(length=120), nullable=False),
        sa.Column("region", sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clinics_clinic_code"), "clinics", ["clinic_code"], unique=True)

    # products
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("canonical_name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("sterile_type", sa.String(length=40), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=30), nullable=False),
        sa.Column("package_qty", sa.Integer(), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_code"], ["clinics.clinic_code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_sku"), "products", ["sku"], unique=False)

    # client_requests
    op.create_table(
        "client_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(length=120), nullable=False),
        sa.Column("clinic_name", sa.String(length=120), nullable=False),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=10), nullable=True),
        sa.Column("intent", sa.String(length=40), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("actions_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("needs_human", sa.Boolean(), nullable=True),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_code"], ["clinics.clinic_code"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ingestion_audit_logs
    op.create_table(
        "ingestion_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_label", sa.String(length=120), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_code"], ["clinics.clinic_code"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # visual_pages
    op.create_table(
        "visual_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_code"], ["clinics.clinic_code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_code", "source_filename", "page_number", name="uq_visual_page"),
    )

    # multi_vector_documents
    op.create_table(
        "multi_vector_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("clinic_code", sa.String(length=40), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("binary_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_code"], ["clinics.clinic_code"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", name="uq_multi_vector_product"),
    )


def downgrade() -> None:
    op.drop_table("multi_vector_documents")
    op.drop_table("visual_pages")
    op.drop_table("ingestion_audit_logs")
    op.drop_table("client_requests")
    op.drop_index(op.f("ix_products_sku"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_clinics_clinic_code"), table_name="clinics")
    op.drop_table("clinics")
