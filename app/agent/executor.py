from ..config import get_settings
from ..db.models import ClientRequest
from ..db.session import SessionLocal
from ..db.vector_store import VectorStore
from ..ingestion.schemas import OrderPayload
from .action_schema import ActionPlan
from .guardrails import unmask_pii
from .tools import (
    extract_quantity,
    extract_requested_date,
    get_product_by_id,
    hybrid_search,
    multi_vector_search,
    product_to_dict,
    visual_search,
)


def _finish(state: dict, session=None) -> dict:
    if session is not None:
        try:
            session.close()
        except Exception:
            pass
    return state


def execute_actions(state: dict, plan: ActionPlan) -> dict:
    """Execute a validated action list against PostgreSQL and ChromaDB."""
    session = None
    if state.get("needs_human"):
        return _finish(state, session)

    session = SessionLocal()
    vector_store = VectorStore()
    threshold = get_settings().confidence_threshold

    best_match: dict | None = None
    checked_product = None
    checked_confidence = 1.0
    order = None
    response = None

    vault = state.get("pii_vault", {})
    for action in plan.actions:
        if action.query and vault:
            action.query = unmask_pii(action.query, vault)
        if action.action == "ask_human":
            state["needs_human"] = True
            state["response"] = {
                "needs_human": True,
                "reason": action.reason or "human escalation requested",
                "confidence_score": action.confidence,
                "products": state.get("matches", []),
            }
            return _finish(state, session)

        if action.confidence < threshold:
            state["needs_human"] = True
            state["response"] = {
                "needs_human": True,
                "reason": "action confidence below threshold",
                "confidence_score": action.confidence,
                "products": state.get("matches", []),
            }
            return _finish(state, session)

        if action.action == "search_product":
            query = action.query or state["masked_text"]
            matches = hybrid_search(
                query,
                state["clinic_code"],
                session,
                vector_store,
            )
            if not matches:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "no approved product in this clinic with available stock",
                    "confidence_score": 0.0,
                    "products": [],
                }
                return _finish(state, session)

            best_match = matches[0]
            best_confidence = best_match["match_confidence"]
            if best_confidence < threshold:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "semantic match confidence below threshold",
                    "confidence_score": best_confidence,
                    "products": matches,
                }
                return _finish(state, session)

            state["matches"] = matches
            state["best_product_id"] = best_match["id"]

        elif action.action == "search_product_multi_vector":
            query = action.query or state["masked_text"]
            try:
                matches = multi_vector_search(query, state["clinic_code"])
            except Exception as exc:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": f"multi-vector retrieval failed: {exc}",
                    "confidence_score": 0.0,
                    "products": [],
                }
                return _finish(state, session)

            if not matches:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "no multi-vector product document in this clinic",
                    "confidence_score": 0.0,
                    "products": [],
                }
                return _finish(state, session)

            best_match = matches[0]
            best_confidence = best_match["match_confidence"]
            if best_confidence < threshold:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "multi-vector match confidence below threshold",
                    "confidence_score": best_confidence,
                    "products": matches,
                }
                return _finish(state, session)

            product_id = best_match.get("product_id")
            if product_id is None:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "multi-vector document has no product mapping",
                    "confidence_score": best_confidence,
                    "products": matches,
                }
                return _finish(state, session)

            state["matches"] = matches
            state["best_product_id"] = product_id

        elif action.action == "search_product_visual":
            query = action.query or state["masked_text"]
            try:
                matches = visual_search(query, state["clinic_code"])
            except Exception as exc:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": f"visual retrieval failed: {exc}",
                    "confidence_score": 0.0,
                    "visual_matches": [],
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            if not matches:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "no visual page match in this clinic",
                    "confidence_score": 0.0,
                    "visual_matches": [],
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            state["visual_matches"] = matches
            state["needs_human"] = True
            state["response"] = {
                "needs_human": True,
                "reason": "visual page match requires human review",
                "confidence_score": matches[0]["match_confidence"],
                "visual_matches": matches,
                "products": state.get("matches", []),
            }
            return _finish(state, session)

        elif action.action == "check_stock":
            product_id = action.product_id or state.get("best_product_id")
            product = (
                get_product_by_id(session, int(product_id))
                if product_id is not None
                else None
            )
            if product is None:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product not found",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            if product.clinic_code != state["clinic_code"]:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product belongs to a different clinic",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            if product.status != "approved":
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product is not approved",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            checked_product = product
            checked_confidence = action.confidence



        elif action.action == "create_order":
            quantity = action.quantity or extract_quantity(state["masked_text"])
            if quantity is None:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "order quantity could not be extracted",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            product_id = action.product_id or state.get("best_product_id")
            product = (
                get_product_by_id(session, int(product_id))
                if product_id is not None
                else None
            )
            if product is None:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product not found",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            if product.clinic_code != state["clinic_code"]:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product belongs to a different clinic",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            if product.status != "approved":
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "product is not approved",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            checked_product = product
            checked_confidence = action.confidence

            if product.stock_quantity < quantity:
                state["needs_human"] = True
                state["response"] = {
                    "needs_human": True,
                    "reason": "requested quantity exceeds available stock",
                    "confidence_score": action.confidence,
                    "products": state.get("matches", []),
                }
                return _finish(state, session)

            requested_by = action.requested_by_date or extract_requested_date(
                state["masked_text"]
            )
            order = OrderPayload(
                product_id=product.id,
                sku=product.sku,
                quantity=quantity,
                client_name=state["client_name"],
                clinic_name=state["clinic_name"],
                clinic_code=state["clinic_code"],
                requested_by_date=requested_by,
                notes="synthetic demo order",
                confidence_score=action.confidence,
            )

            request = ClientRequest(
                client_name=order.client_name,
                clinic_name=order.clinic_name,
                clinic_code=order.clinic_code,
                request_text=state["masked_text"],
                product_id=order.product_id,
                quantity=order.quantity,
                requested_by_date=order.requested_by_date,
                needs_human=False,
                confidence_score=order.confidence_score,
            )
            session.add(request)


        elif action.action == "respond":
            response = {
                "needs_human": False,
                "language": action.language or state["language"],
                "message": action.message or "Action plan completed.",
                "confidence_score": action.confidence,
                "products": state.get("matches", []),
            }

    if state.get("needs_human"):
        return _finish(state, session)

    if order is not None:
        session.commit()
        state["order"] = order.model_dump()
        state["response"] = {
            "needs_human": False,
            "language": state["language"],
            "confidence_score": order.confidence_score,
            "order": order.model_dump(),
            "products": state.get("matches", []),
        }
        return _finish(state, session)

    if response is not None:
        state["response"] = response
        return _finish(state, session)

    if checked_product is not None:
        state["response"] = {
            "needs_human": False,
            "language": state["language"],
            "confidence_score": checked_confidence,
            "products": [product_to_dict(checked_product)],
        }
        return _finish(state, session)

    if best_match is not None:
        state["response"] = {
            "needs_human": False,
            "language": state["language"],
            "confidence_score": best_match["match_confidence"],
            "products": state.get("matches", []),
        }
        return _finish(state, session)

    state["needs_human"] = True
    state["response"] = {
        "needs_human": True,
        "reason": "no executable action produced a result",
        "confidence_score": 0.0,
        "products": [],
    }
    return _finish(state, session)
