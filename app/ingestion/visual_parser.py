from pathlib import Path

import pymupdf

from ..db.visual_store import get_visual_store


def render_pdf_pages(path: str | Path, dpi: int = 150) -> list[bytes]:
    """Render PDF pages as images for OCR-free visual retrieval."""
    document = pymupdf.open(path)
    pages: list[bytes] = []

    for page in document:
        pixmap = page.get_pixmap(dpi=dpi)
        pages.append(pixmap.tobytes("png"))

    return pages


def render_pdf_pages_from_bytes(data: bytes, dpi: int = 150) -> list[bytes]:
    """Render PDF pages from uploaded bytes."""
    document = pymupdf.open(stream=data, filetype="pdf")
    pages: list[bytes] = []

    for page in document:
        pixmap = page.get_pixmap(dpi=dpi)
        pages.append(pixmap.tobytes("png"))

    return pages


def store_visual_pages(
    data: bytes,
    clinic_code: str,
    source_label: str,
    product_id: int | None = None,
) -> int:
    """Store synthetic PDF page images and v6.0 visual token vectors."""
    pages = render_pdf_pages_from_bytes(data)
    store = get_visual_store()

    for page_number, image_bytes in enumerate(pages, start=1):
        store.store_page(
            image_bytes=image_bytes,
            clinic_code=clinic_code,
            source_label=source_label,
            page_number=page_number,
            product_id=product_id,
        )

    return len(pages)
