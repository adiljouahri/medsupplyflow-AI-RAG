import pytest
from pydantic import ValidationError

from app.agent.action_schema import ActionPlan


def test_action_plan_allows_known_action() -> None:
    plan = ActionPlan.model_validate(
        {
            "actions": [
                {
                    "action": "search_product",
                    "clinic_code": "demo-clinic-a",
                    "query": "scalpel",
                    "confidence": 0.9,
                }
            ]
        }
    )
    assert plan.actions[0].action == "search_product"


def test_action_plan_rejects_unknown_action() -> None:
    payload = {
        "actions": [
            {
                "action": "delete_product",
                "clinic_code": "demo-clinic-a",
                "confidence": 1.0,
            }
        ]
    }
    with pytest.raises(ValidationError, match="delete_product"):
        ActionPlan.model_validate(payload)


def test_action_plan_rejects_missing_clinic_code() -> None:
    payload = {
        "actions": [
            {
                "action": "respond",
                "confidence": 1.0,
                "message": "ok",
            }
        ]
    }
    with pytest.raises(ValidationError, match="clinic_code"):
        ActionPlan.model_validate(payload)
