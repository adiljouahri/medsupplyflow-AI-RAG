from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ingestion.schemas import ClinicCode

ActionName = Literal[
    "search_product",
    "search_product_multi_vector",
    "search_product_visual",
    "check_stock",
    "create_order",
    "respond",
    "ask_human",
]
LanguageCode = Literal["en", "es", "de"]


class AgentAction(BaseModel):
    """One validated action in the planner's JSON action list."""

    action: ActionName
    clinic_code: ClinicCode
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    query: str | None = Field(default=None, max_length=200)
    product_id: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1, le=10_000)
    requested_by_date: date | None = None
    language: LanguageCode | None = None
    message: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class ActionPlan(BaseModel):
    """The planner must return only an explicit action list."""

    actions: list[AgentAction] = Field(..., min_length=1, max_length=8)

    model_config = ConfigDict(extra="forbid")
