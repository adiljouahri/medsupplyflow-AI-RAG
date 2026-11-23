from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ClinicCode = Literal["demo-clinic-a", "demo-clinic-b", "demo-clinic-c"]


class SurgicalItem(BaseModel):
    """Strict normalized surgical item. Extra fields are rejected."""

    sku: str = Field(..., min_length=3, max_length=80)
    canonical_name: str = Field(..., min_length=3, max_length=180)
    category: str = Field(..., min_length=2, max_length=80)
    sterile_type: str = Field(..., min_length=2, max_length=40)
    unit_of_measure: str = Field(..., min_length=1, max_length=30)
    package_qty: int = Field(..., ge=1, le=10_000)
    stock_quantity: int = Field(default=0, ge=0, le=10_000_000)
    notes: str = Field(default="", max_length=500)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    status: Literal["approved", "needs_review"] = "needs_review"

    model_config = ConfigDict(extra="forbid")

    @field_validator("sku", "canonical_name", "category", "sterile_type", "unit_of_measure")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be blank")
        return value


class RequestInput(BaseModel):
    client_name: str = Field(..., min_length=2, max_length=100)
    clinic_name: str = Field(..., min_length=2, max_length=100)
    clinic_code: ClinicCode
    request_text: str = Field(..., min_length=3, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class OrderPayload(BaseModel):
    product_id: int = Field(..., ge=1)
    sku: str = Field(..., min_length=3, max_length=80)
    quantity: int = Field(..., ge=1, le=10_000)
    client_name: str = Field(..., min_length=2, max_length=100)
    clinic_name: str = Field(..., min_length=2, max_length=100)
    clinic_code: ClinicCode
    requested_by_date: date | None = None
    notes: str = Field(default="", max_length=500)
    confidence_score: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")
