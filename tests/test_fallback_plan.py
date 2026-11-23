from app.agent.graph import fallback_plan


def test_order_fallback_plan() -> None:
    plan = fallback_plan("Send 5 units by 2026-06-30", "demo-clinic-a")
    actions = [action.action for action in plan.actions]
    assert actions == ["search_product", "check_stock", "create_order"]


def test_inquiry_fallback_plan() -> None:
    plan = fallback_plan(
        "Do you have 3-0 stitching thread available?",
        "demo-clinic-b",
    )
    actions = [action.action for action in plan.actions]
    assert actions == ["search_product", "respond"]


def test_unknown_intent_fallback_plan() -> None:
    plan = fallback_plan("Hello", "demo-clinic-c")
    assert plan.actions[0].action == "ask_human"
