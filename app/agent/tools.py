import re
from datetime import date
from typing import cast

from sqlalchemy import select

from ..db.models import Product
from ..db.multi_vector_store import get_multi_vector_store
from ..db.session import SessionLocal
from ..db.vector_store import VectorStore
from ..db.visual_store import get_visual_store

QUANTITY_PATTERN = re.compile(
    r"(\d+)\s*(?:boxes?|box|units?|unit|pcs?|pieces?|pack|packs|vials?|bottles?)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def product_to_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "sku": product.sku,
        "canonical_name": product.canonical_name,
        "category": product.category,
        "sterile_type": product.sterile_type,
        "unit_of_measure": product.unit_of_measure,
        "package_qty": product.package_qty,
        "stock_quantity": product.stock_quantity,
        "status": product.status,
        "confidence_score": product.confidence_score,
        "clinic_code": product.clinic_code,
    }


def get_product_by_id(session, product_id: int) -> Product | None:
    return cast(
        Product | None,
        session.execute(
            select(Product).where(Product.id == product_id)
        ).scalar_one_or_none(),
    )


def extract_quantity(text: str) -> int | None:
    match = QUANTITY_PATTERN.search(text)
    if not match:
        return None
    quantity = int(match.group(1))
    return quantity if quantity > 0 else None


def extract_requested_date(text: str) -> date | None:
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def hybrid_search(
    query: str,
    clinic_code: str,
    session=None,
    vector_store=None,
    limit: int = 5,
) -> list[dict]:
    """Chroma semantic shortlist, then PostgreSQL exact availability check."""
    owned = session is None
    session = session or SessionLocal()
    vector_store = vector_store or VectorStore()

    try:
        semantic = vector_store.query(query, limit=limit, clinic_code=clinic_code)
        ids: list[int] = []
        distances: dict[int, float] = {}
        for match in semantic:
            try:
                product_id = int(match["id"])
            except (ValueError, TypeError):
                continue
            ids.append(product_id)
            distances[product_id] = float(match.get("distance", 0.0))

        if ids:
            products = session.execute(
                select(Product).where(
                    Product.id.in_(ids),
                    Product.clinic_code == clinic_code,
                    Product.status == "approved",
                    Product.stock_quantity > 0,
                )
            ).scalars().all()
        else:
            products = []

        if not products:
            term = query.strip().split()[0] if query.strip() else ""
            products = session.execute(
                select(Product).where(
                    Product.canonical_name.ilike(f"%{term}%"),
                    Product.clinic_code == clinic_code,
                    Product.status == "approved",
                    Product.stock_quantity > 0,
                ).limit(limit)
            ).scalars().all()

        result: list[dict] = []
        for product in products:
            payload = product_to_dict(product)
            payload["semantic_distance"] = distances.get(product.id)
            payload["match_confidence"] = max(
                0.0, min(1.0, 1.0 - distances.get(product.id, 1.0))
            )
            result.append(payload)

        return result
    finally:
        if owned:
            session.close()


def multi_vector_search(
    query: str,
    clinic_code: str,
    limit: int = 5,
) -> list[dict]:
    """ColBERT-style MaxSim retrieval over synthetic product documents."""
    return get_multi_vector_store().search(query, clinic_code, limit=limit)


def visual_search(
    query: str,
    clinic_code: str,
    limit: int = 5,
) -> list[dict]:
    """Text-query-to-page-image retrieval without OCR preprocessing."""
    return get_visual_store().search(query, clinic_code, limit=limit)
