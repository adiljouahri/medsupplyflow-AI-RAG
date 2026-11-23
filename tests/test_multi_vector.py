import pytest

from app.agent.action_schema import ActionPlan

try:
    from sentence_transformers import MultiVectorEncoder
except ImportError:
    MultiVectorEncoder = None


def test_multi_vector_encoder_is_available() -> None:
    if MultiVectorEncoder is None:
        pytest.skip("sentence-transformers is not installed")
    assert callable(MultiVectorEncoder)


def test_multi_vector_action_is_allowed() -> None:
    plan = ActionPlan.model_validate(
        {
            "actions": [
                {
                    "action": "search_product_multi_vector",
                    "clinic_code": "demo-clinic-a",
                    "query": "synthetic scalpel",
                    "confidence": 0.9,
                }
            ]
        }
    )
    assert plan.actions[0].action == "search_product_multi_vector"


def test_visual_action_is_allowed() -> None:
    plan = ActionPlan.model_validate(
        {
            "actions": [
                {
                    "action": "search_product_visual",
                    "clinic_code": "demo-clinic-a",
                    "query": "synthetic catalog page",
                    "confidence": 0.9,
                }
            ]
        }
    )
    assert plan.actions[0].action == "search_product_visual"
