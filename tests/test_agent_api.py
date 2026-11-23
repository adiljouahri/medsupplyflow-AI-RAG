from app.agent.graph import classify_intent
from app.agent.tools import extract_quantity, extract_requested_date
from app.ingestion.schemas import RequestInput, OrderPayload
from pydantic import ValidationError


def test_order_intent_classification() -> None:
    assert classify_intent("Send 10 boxes of #15 scalpels to Clinic North by Friday") == "order"


def test_product_inquiry_classification() -> None:
    assert classify_intent("Do you have 3-0 stitching thread available?") == "product_inquiry"


def test_missing_quantity_escalates() -> None:
    assert classify_intent("Send scalpels to Clinic North") == "human_escalation"


def test_quantity_extraction() -> None:
    assert extract_quantity("Send 10 boxes of #15 scalpels") == 10


def test_date_extraction() -> None:
    value = extract_requested_date("Send 5 units by 2026-06-30")
    assert value is not None
    assert value.isoformat() == "2026-06-30"


def test_request_input_rejects_extra_pii_field() -> None:
    payload = {
        "client_name": "Clinic North",
        "clinic_name": "Demo Clinic",
        "clinic_code": "demo-clinic-a",
        "request_text": "Send 10 boxes of #15 scalpels",
        "patient_id": "123",
    }
    try:
        RequestInput.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("extra fields should be rejected")


def test_order_payload_rejects_negative_quantity() -> None:
    payload = {
        "product_id": 1,
        "sku": "SC-15",
        "quantity": -1,
        "client_name": "Clinic North",
        "clinic_name": "Demo Clinic",
        "clinic_code": "demo-clinic-a",
        "requested_by_date": None,
        "notes": "bad order",
        "confidence_score": 0.9,
    }
    try:
        OrderPayload.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("negative quantity should be rejected")


def test_request_input_rejects_unknown_clinic() -> None:
    payload = {
        "client_name": "Clinic North",
        "clinic_name": "Demo Clinic",
        "clinic_code": "demo-clinic-x",
        "request_text": "Send 5 units by 2026-06-30",
    }
    try:
        RequestInput.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown clinic code should be rejected")
