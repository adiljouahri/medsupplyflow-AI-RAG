from app.db.models import Product
from app.ingestion.normalizer import build_item, is_probable_duplicate, normalize_rows
from app.ingestion.schemas import SurgicalItem
from pydantic import ValidationError


class MockLLM:
    """Mock provider so tests run without any paid API key."""

    def extract_item(self, raw: dict[str, str]) -> dict:
        if "corrupt" in raw.get("description", "").lower():
            return {
                "sku": "BAD",
                "canonical_name": "",
                "category": "unknown",
                "sterile_type": "sterile",
                "unit_of_measure": "pack",
                "package_qty": 0,
                "stock_quantity": 0,
                "notes": "corrupt row",
                "confidence_score": 1.5,
                "status": "approved",
            }
        return {
            "sku": "SC-15",
            "canonical_name": "Sterile Scalpel #15",
            "category": "surgical instrument",
            "sterile_type": "sterile",
            "unit_of_measure": "pcs",
            "package_qty": 10,
            "stock_quantity": 10,
            "notes": "stainless steel",
            "confidence_score": 0.92,
            "status": "approved",
        }


def test_pydantic_rejects_invalid_corrupted_data() -> None:
    try:
        SurgicalItem.model_validate(MockLLM().extract_item({"description": "corrupt"}))
    except ValidationError as exc:
        assert "package_qty" in str(exc) or "canonical_name" in str(exc)
    else:
        raise AssertionError("invalid item should have been rejected")


def test_low_confidence_flags_needs_review() -> None:
    item = build_item(
        {
            "sku": "SC-15",
            "canonical_name": "Sterile Scalpel #15",
            "category": "surgical instrument",
            "sterile_type": "sterile",
            "unit_of_measure": "pcs",
            "package_qty": 10,
            "stock_quantity": 10,
            "notes": "stainless steel",
            "confidence_score": 0.62,
            "status": "approved",
        },
        threshold=0.85,
    )
    assert item.status == "needs_review"


def test_duplicate_product_detection() -> None:
    existing = Product(
        sku="SC-15",
        canonical_name="Sterile Scalpel #15",
        category="surgical instrument",
        sterile_type="sterile",
        unit_of_measure="pcs",
        package_qty=10,
        stock_quantity=10,
        notes="stainless steel",
        confidence_score=0.9,
        status="approved",
    )
    candidate = SurgicalItem(
        sku="SC-15",
        canonical_name="Sterile Scalpel #15",
        category="surgical instrument",
        sterile_type="sterile",
        unit_of_measure="pcs",
        package_qty=10,
        stock_quantity=10,
        notes="stainless steel",
        confidence_score=0.92,
        status="approved",
    )
    assert is_probable_duplicate(existing, candidate)
    assert is_probable_duplicate(existing, candidate.model_copy(update={"sku": "SC-16"}))


def test_mock_normalization() -> None:
    rows = [
        {"description": "Sterile Scalpel #15", "unit_hint": "pcs"},
        {"description": "corrupt row", "unit_hint": "pack"},
    ]
    normalized = normalize_rows(rows, MockLLM(), threshold=0.85)
    assert len(normalized) == 1
    assert normalized[0].status == "approved"
