from app.ingestion.visual_parser import render_pdf_pages_from_bytes, store_visual_pages


def test_visual_parser_entry_points_exist() -> None:
    assert callable(render_pdf_pages_from_bytes)
    assert callable(store_visual_pages)
