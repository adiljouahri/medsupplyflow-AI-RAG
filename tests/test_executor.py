"""Executor tests: the action loop against SQLite with a faked Chroma shortlist.

Every branch that matters for safety is covered here: tenant isolation,
approval status, stock limits, confidence thresholds, and human escalation.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.agent import executor as executor_module
from app.agent.action_schema import ActionPlan, AgentAction
from app.db.models import ClientRequest

CLINIC = "demo-clinic-a"


def make_state(**overrides) -> dict:
    state = {
        "client_name": "Clinic North",
        "clinic_name": "Demo Clinic A",
        "clinic_code": CLINIC,
        "masked_text": "Send 10 boxes of Sterile Scalpel #15 by 2026-06-30",
        "language": "en",
        "needs_human": False,
        "matches": [],
    }
    state.update(overrides)
    return state


def make_plan(*actions: AgentAction) -> ActionPlan:
    return ActionPlan(actions=list(actions))


def act(action: str, **overrides) -> AgentAction:
    return AgentAction(action=action, clinic_code=CLINIC, **overrides)


def stored_requests(session_factory) -> list[ClientRequest]:
    with session_factory() as session:
        return list(session.execute(select(ClientRequest)).scalars().all())


@pytest.fixture()
def wired_store(session_factory, fake_vector_store, monkeypatch):
    """Point the executor at SQLite and the fake Chroma client."""
    monkeypatch.setattr(executor_module, "SessionLocal", session_factory)
    monkeypatch.setattr(executor_module, "VectorStore", lambda: fake_vector_store)
    return fake_vector_store


def test_order_flow_searches_checks_stock_and_persists_the_request(
    wired_store,
    product_factory,
    session_factory,
) -> None:
    product = product_factory(sku="SC-15", stock_quantity=50, status="approved")
    wired_store.matches = [{"id": str(product.id), "distance": 0.05}]

    plan = make_plan(
        act("search_product", query="Sterile Scalpel #15"),
        act("check_stock"),
        act("create_order", quantity=10),
    )
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is False
    assert state["response"]["needs_human"] is False
    assert state["order"]["sku"] == "SC-15"
    assert state["order"]["quantity"] == 10
    assert state["order"]["requested_by_date"] == date(2026, 6, 30)
    assert wired_store.queries[0][1] == CLINIC

    requests = stored_requests(session_factory)
    assert len(requests) == 1
    assert requests[0].product_id == product.id
    assert requests[0].quantity == 10
    assert requests[0].clinic_code == CLINIC


def test_search_shortlist_is_filtered_to_the_calling_clinic(
    wired_store,
    product_factory,
) -> None:
    foreign = product_factory(sku="SC-15", clinic_code="demo-clinic-b", stock_quantity=50)
    wired_store.matches = [{"id": str(foreign.id), "distance": 0.01}]

    plan = make_plan(act("search_product", query="Sterile Scalpel #15"))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == (
        "no approved product in this clinic with available stock"
    )


def test_check_stock_blocks_a_product_from_another_clinic(
    wired_store,
    product_factory,
) -> None:
    foreign = product_factory(sku="SC-15", clinic_code="demo-clinic-b")

    plan = make_plan(act("check_stock", product_id=foreign.id))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "product belongs to a different clinic"


def test_check_stock_blocks_an_unapproved_product(
    wired_store,
    product_factory,
) -> None:
    pending = product_factory(sku="SC-15", status="needs_review")

    plan = make_plan(act("check_stock", product_id=pending.id))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "product is not approved"


def test_check_stock_blocks_a_missing_product(wired_store) -> None:
    plan = make_plan(act("check_stock", product_id=4242))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "product not found"


def test_create_order_blocks_when_stock_is_insufficient(
    wired_store,
    product_factory,
    session_factory,
) -> None:
    product = product_factory(sku="SC-15", stock_quantity=5, status="approved")

    plan = make_plan(act("create_order", product_id=product.id, quantity=10))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "requested quantity exceeds available stock"
    assert stored_requests(session_factory) == []


def test_create_order_without_a_quantity_escalates(
    wired_store,
    product_factory,
) -> None:
    product = product_factory(sku="SC-15", stock_quantity=50, status="approved")

    plan = make_plan(act("create_order", product_id=product.id))
    state = executor_module.execute_actions(
        make_state(masked_text="Send scalpels to Clinic North"),
        plan,
    )

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "order quantity could not be extracted"


def test_search_without_any_match_escalates(wired_store) -> None:
    wired_store.matches = []

    plan = make_plan(act("search_product", query="hydrogel wound dressing"))
    state = executor_module.execute_actions(
        make_state(masked_text="hydrogel wound dressing"),
        plan,
    )

    assert state["needs_human"] is True
    assert state["response"]["reason"] == (
        "no approved product in this clinic with available stock"
    )


def test_semantic_match_below_threshold_escalates(
    wired_store,
    product_factory,
) -> None:
    product = product_factory(sku="SC-15", stock_quantity=50, status="approved")
    wired_store.matches = [{"id": str(product.id), "distance": 0.95}]

    plan = make_plan(act("search_product", query="Sterile Scalpel #15"))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "semantic match confidence below threshold"


def test_action_below_confidence_threshold_escalates(wired_store) -> None:
    plan = make_plan(act("search_product", query="scalpel", confidence=0.4))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "action confidence below threshold"


def test_ask_human_short_circuits_the_plan(
    wired_store,
    session_factory,
) -> None:
    plan = make_plan(act("ask_human", reason="manual review required", confidence=0.0))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "manual review required"
    assert stored_requests(session_factory) == []


def test_a_state_already_flagged_for_a_human_runs_no_actions(
    wired_store,
    session_factory,
) -> None:
    plan = make_plan(act("create_order", product_id=1, quantity=10))
    state = executor_module.execute_actions(make_state(needs_human=True), plan)

    assert "response" not in state
    assert wired_store.queries == []
    assert stored_requests(session_factory) == []


def test_respond_action_returns_the_planners_message(wired_store) -> None:
    plan = make_plan(
        act("respond", message="Stock is available.", language="de", confidence=0.95)
    )
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is False
    assert state["response"]["message"] == "Stock is available."
    assert state["response"]["language"] == "de"


def test_multi_vector_match_maps_back_to_a_product_and_orders_it(
    wired_store,
    product_factory,
    session_factory,
    monkeypatch,
) -> None:
    product = product_factory(sku="SC-15", stock_quantity=50, status="approved")

    def _search(_query: str, _clinic_code: str, limit: int = 5) -> list[dict]:
        return [{"product_id": product.id, "match_confidence": 0.93, "score": 5.2}]

    monkeypatch.setattr(executor_module, "multi_vector_search", _search)

    plan = make_plan(
        act("search_product_multi_vector", query="scalpel page match"),
        act("create_order", quantity=6),
    )
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is False
    assert state["order"]["product_id"] == product.id
    assert len(stored_requests(session_factory)) == 1


def test_multi_vector_failure_escalates_instead_of_raising(
    wired_store,
    monkeypatch,
) -> None:
    def _boom(_query: str, _clinic_code: str, limit: int = 5):
        raise RuntimeError("advanced retrieval dependencies are not installed")

    monkeypatch.setattr(executor_module, "multi_vector_search", _boom)

    plan = make_plan(act("search_product_multi_vector", query="scalpel"))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"].startswith("multi-vector retrieval failed")


def test_visual_match_always_goes_to_a_human(
    wired_store,
    product_factory,
    monkeypatch,
) -> None:
    product = product_factory(sku="SC-15", status="approved")

    def _search(_query: str, _clinic_code: str, limit: int = 5) -> list[dict]:
        return [{"product_id": product.id, "page_number": 3, "match_confidence": 0.88}]

    monkeypatch.setattr(executor_module, "visual_search", _search)

    plan = make_plan(act("search_product_visual", query="scalpel catalog page"))
    state = executor_module.execute_actions(make_state(), plan)

    assert state["needs_human"] is True
    assert state["response"]["reason"] == "visual page match requires human review"
    assert state["response"]["visual_matches"][0]["page_number"] == 3
