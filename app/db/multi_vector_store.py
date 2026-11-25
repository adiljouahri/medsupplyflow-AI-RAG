from sqlalchemy import select

from ..config import get_settings
from ..db.models import MultiVectorDocument
from ..db.session import SessionLocal


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _maxsim(query_vectors: list[list[float]], document_vectors: list[list[float]]) -> float:
    if not document_vectors:
        return 0.0

    total = 0.0
    for query_vector in query_vectors:
        best = max(_dot(query_vector, document_vector) for document_vector in document_vectors)
        total += best
    return total / max(1, len(query_vectors))


class MultiVectorStore:
    """PostgreSQL-backed token-vector store for ColBERT-style late interaction."""

    def __init__(self) -> None:
        settings = get_settings()
        try:
            from sentence_transformers import MultiVectorEncoder
        except ImportError as exc:
            raise RuntimeError(
                "advanced retrieval dependencies are not installed"
            ) from exc
        self.model = MultiVectorEncoder(settings.multi_vector_model)

    def store_document(
        self,
        text: str,
        clinic_code: str,
        source_label: str,
        document_label: str,
        product_id: int | None = None,
    ) -> int:
        token_vectors = self.model.encode_document([text])[0].tolist()
        session = SessionLocal()
        try:
            if product_id is not None:
                existing = session.execute(
                    select(MultiVectorDocument).where(
                        MultiVectorDocument.product_id == product_id,
                        MultiVectorDocument.clinic_code == clinic_code,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    session.delete(existing)
                    session.commit()

            document = MultiVectorDocument(
                clinic_code=clinic_code,
                product_id=product_id,
                source_label=source_label,
                document_label=document_label,
                document_text=text,
                token_vectors=token_vectors,
            )
            session.add(document)
            session.commit()
            return int(document.id)
        finally:
            session.close()

    def store_product_document(self, product) -> int:
        text = (
            f"{product.canonical_name} | {product.category} | "
            f"{product.sterile_type} | {product.unit_of_measure} | "
            f"package qty {product.package_qty} | SKU {product.sku}"
        )
        return self.store_document(
            text=text,
            clinic_code=product.clinic_code,
            source_label="synthetic approved product",
            document_label=product.sku,
            product_id=product.id,
        )

    def search(self, query: str, clinic_code: str, limit: int = 5) -> list[dict]:
        query_vectors = self.model.encode_query([query])[0].tolist()
        session = SessionLocal()
        try:
            documents = session.execute(
                select(MultiVectorDocument).where(
                    MultiVectorDocument.clinic_code == clinic_code
                )
            ).scalars().all()

            matches: list[dict] = []
            for document in documents:
                score = _maxsim(query_vectors, document.token_vectors)
                matches.append(
                    {
                        "id": document.id,
                        "product_id": document.product_id,
                        "clinic_code": document.clinic_code,
                        "document_label": document.document_label,
                        "source_label": document.source_label,
                        "document": document.document_text,
                        "score": score,
                        "match_confidence": max(0.0, min(1.0, score)),
                    }
                )

            matches.sort(key=lambda item: item["score"], reverse=True)
            return matches[: max(1, limit)]
        finally:
            session.close()


_MULTI_VECTOR_STORE: MultiVectorStore | None = None


def get_multi_vector_store() -> MultiVectorStore:
    global _MULTI_VECTOR_STORE
    if _MULTI_VECTOR_STORE is None:
        _MULTI_VECTOR_STORE = MultiVectorStore()
    return _MULTI_VECTOR_STORE


def delete_product_document(product_id: int, clinic_code: str) -> None:
    with SessionLocal() as session:
        existing = session.execute(
            select(MultiVectorDocument).where(
                MultiVectorDocument.product_id == product_id,
                MultiVectorDocument.clinic_code == clinic_code,
            )
        ).scalar_one_or_none()
        if existing is not None:
            session.delete(existing)
            session.commit()
