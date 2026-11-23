from io import BytesIO

from PIL import Image
from sqlalchemy import select

from ..config import get_settings
from ..db.models import VisualPage
from ..db.session import SessionLocal


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _maxsim(query_vectors: list[list[float]], document_vectors: list[list[float]]) -> float:
    if not document_vectors:
        return 0.0

    total = 0.0
    for query_vector in query_vectors:
        best = max(_dot(query_vector, document_vector) for document_vector in document_vectors)
        total += best
    return total / max(1, len(query_vectors))


class VisualMultiVectorStore:
    """PostgreSQL-backed page-image store for OCR-free visual retrieval."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.visual_model:
            raise ValueError("VISUAL_MODEL is required for visual retrieval")
        try:
            from sentence_transformers import MultiVectorEncoder
        except ImportError as exc:
            raise RuntimeError(
                "advanced visual retrieval dependencies are not installed"
            ) from exc
        self.model = MultiVectorEncoder(settings.visual_model)

    def store_page(
        self,
        image_bytes: bytes,
        clinic_code: str,
        source_label: str,
        page_number: int,
        product_id: int | None = None,
    ) -> int:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        token_vectors = self.model.encode_document([image])[0].tolist()

        session = SessionLocal()
        try:
            existing = session.execute(
                select(VisualPage).where(
                    VisualPage.clinic_code == clinic_code,
                    VisualPage.source_label == source_label,
                    VisualPage.page_number == page_number,
                )
            ).scalar_one_or_none()
            if existing is not None:
                session.delete(existing)
                session.commit()

            page = VisualPage(
                clinic_code=clinic_code,
                product_id=product_id,
                source_label=source_label,
                page_number=page_number,
                image=image_bytes,
                token_vectors=token_vectors,
            )
            session.add(page)
            session.commit()
            return page.id
        finally:
            session.close()

    def search(self, query: str, clinic_code: str, limit: int = 5) -> list[dict]:
        query_vectors = self.model.encode_query([query])[0].tolist()
        session = SessionLocal()
        try:
            pages = session.execute(
                select(VisualPage).where(VisualPage.clinic_code == clinic_code)
            ).scalars().all()

            matches: list[dict] = []
            for page in pages:
                score = _maxsim(query_vectors, page.token_vectors)
                matches.append(
                    {
                        "id": page.id,
                        "product_id": page.product_id,
                        "clinic_code": page.clinic_code,
                        "source_label": page.source_label,
                        "page_number": page.page_number,
                        "score": score,
                        "match_confidence": max(0.0, min(1.0, score)),
                    }
                )

            matches.sort(key=lambda item: item["score"], reverse=True)
            return matches[: max(1, limit)]
        finally:
            session.close()


_VISUAL_STORE: VisualMultiVectorStore | None = None


def get_visual_store() -> VisualMultiVectorStore:
    global _VISUAL_STORE
    if _VISUAL_STORE is None:
        _VISUAL_STORE = VisualMultiVectorStore()
    return _VISUAL_STORE
