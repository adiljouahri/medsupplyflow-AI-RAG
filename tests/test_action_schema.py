from app.agent.action_schema import ActionPlan
from pydantic import ValidationError


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
    try:
        ActionPlan.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown action should be rejected")


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
    try:
        ActionPlan.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("missing clinic code should be rejected")
