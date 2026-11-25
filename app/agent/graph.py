import re
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from .action_schema import ActionPlan, AgentAction
from .executor import execute_actions
from .guardrails import UnsafeRequest, validate_request
from .language import detect_supported_language
from .planner import LLMPlanner
from .tools import extract_quantity

DEMO_CLINIC_CODES = {"demo-clinic-a", "demo-clinic-b", "demo-clinic-c"}

ORDER_VERB = re.compile(
    r"\b(?:send|order|deliver|ship|buy|purchase|dispatch|request)\b",
    re.IGNORECASE,
)
INQUIRY_VERB = re.compile(
    r"\b(?:do you have|available|availability|what is|which|how many|stock|look up|find)\b",
    re.IGNORECASE,
)


def classify_intent(text: str) -> Literal["product_inquiry", "order", "human_escalation"]:
    quantity = extract_quantity(text)
    if ORDER_VERB.search(text) and quantity is not None:
        return "order"
    if ORDER_VERB.search(text) and quantity is None:
        return "human_escalation"
    if INQUIRY_VERB.search(text):
        return "product_inquiry"
    return "product_inquiry"


class AgentState(TypedDict, total=False):
    request_text: str
    client_name: str
    clinic_name: str
    clinic_code: str
    masked_text: str
    language: str
    needs_human: bool
    plan: ActionPlan
    actions: list[dict]
    matches: list[dict]
    visual_matches: list[dict]
    best_product_id: int
    order: dict
    response: dict


def fallback_plan(text: str, clinic_code: str) -> ActionPlan:
    """Deterministic demo planner used when no LLM key is configured."""
    quantity = extract_quantity(text)

    if ORDER_VERB.search(text) and quantity is not None:
        actions = [
            AgentAction(
                action="search_product",
                clinic_code=clinic_code,
                query=text,
                confidence=1.0,
            ),
            AgentAction(
                action="check_stock",
                clinic_code=clinic_code,
                confidence=1.0,
            ),
            AgentAction(
                action="create_order",
                clinic_code=clinic_code,
                quantity=quantity,
                confidence=1.0,
            ),
        ]
        return ActionPlan(actions=actions)

    if ORDER_VERB.search(text) and quantity is None:
        return ActionPlan(
            actions=[
                AgentAction(
                    action="ask_human",
                    clinic_code=clinic_code,
                    confidence=0.0,
                    reason="order quantity could not be extracted",
                )
            ]
        )

    if INQUIRY_VERB.search(text):
        return ActionPlan(
            actions=[
                AgentAction(
                    action="search_product",
                    clinic_code=clinic_code,
                    query=text,
                    confidence=1.0,
                ),
                AgentAction(
                    action="respond",
                    clinic_code=clinic_code,
                    confidence=1.0,
                ),
            ]
        )

    return ActionPlan(
        actions=[
            AgentAction(
                action="ask_human",
                clinic_code=clinic_code,
                confidence=0.0,
                reason="request intent could not be determined",
            )
        ]
    )


def guardrail_node(state: AgentState) -> AgentState:
    if state["clinic_code"] not in DEMO_CLINIC_CODES:
        state["needs_human"] = True
        state["response"] = {
            "needs_human": True,
            "reason": "unknown synthetic clinic code",
            "confidence_score": 0.0,
            "products": [],
        }
        return state

    try:
        state["masked_text"] = validate_request(state["request_text"])
    except UnsafeRequest as exc:
        state["needs_human"] = True
        state["response"] = {
            "needs_human": True,
            "reason": str(exc),
            "confidence_score": 0.0,
            "products": [],
        }
        return state

    state["needs_human"] = False
    return state


def language_node(state: AgentState) -> AgentState:
    if state.get("needs_human"):
        return state

    language = detect_supported_language(state["masked_text"])
    if language is None:
        state["needs_human"] = True
        state["response"] = {
            "needs_human": True,
            "reason": "unsupported or ambiguous language",
            "confidence_score": 0.0,
            "products": [],
        }
        return state

    state["language"] = language
    return state


def planner_node(state: AgentState) -> AgentState:
    if state.get("needs_human"):
        return state

    settings = get_settings()
    if settings.llm_api_key or settings.llm_model.startswith("ollama/"):
        try:
            plan = LLMPlanner(settings).plan_actions(
                state["masked_text"], state["clinic_code"]
            )
        except Exception as exc:
            state["needs_human"] = True
            state["response"] = {
                "needs_human": True,
                "reason": f"planner failed: {exc}",
                "confidence_score": 0.0,
                "products": [],
            }
            return state
    else:
        plan = fallback_plan(state["masked_text"], state["clinic_code"])

    state["plan"] = plan
    state["actions"] = plan.model_dump()["actions"]
    return state


def executor_node(state: AgentState) -> AgentState:
    if state.get("needs_human"):
        return state
    return execute_actions(state, state["plan"])


workflow = StateGraph(AgentState)
workflow.add_node("guardrails", guardrail_node)
workflow.add_node("language", language_node)
workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_edge(START, "guardrails")
workflow.add_edge("guardrails", "language")
workflow.add_edge("language", "planner")
workflow.add_edge("planner", "executor")
workflow.add_edge("executor", END)
agent_graph = workflow.compile()


def run_request(
    client_name: str,
    clinic_name: str,
    clinic_code: str,
    request_text: str,
) -> dict:
    config = {
        "tags": ["medsupplyflow", "agent_graph", clinic_code],
        "metadata": {
            "client_name": client_name,
            "clinic_name": clinic_name,
            "clinic_code": clinic_code,
        },
    }
    result = agent_graph.invoke(
        {
            "request_text": request_text,
            "client_name": client_name,
            "clinic_name": clinic_name,
            "clinic_code": clinic_code,
        },
        config=config,
    )
    return result.get("response", {})
