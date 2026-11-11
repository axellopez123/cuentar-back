import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CardType


class CardBase(BaseModel):
    alias: str = Field(..., min_length=2, max_length=100)
    card_type: CardType
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0)
    current_balance: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_budget_limit: Optional[Decimal] = Field(None, ge=0)
    statement_closing_day: Optional[int] = Field(None, ge=1, le=31)
    payment_due_day: Optional[int] = Field(None, ge=1, le=31)
    color_hex: Optional[str] = Field(default="#2563EB", max_length=7)


class CardCreate(CardBase):
    user_id: Optional[uuid.UUID] = None


class CardUpdate(BaseModel):
    alias: Optional[str] = Field(None, min_length=2, max_length=100)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    monthly_budget_limit: Optional[Decimal] = Field(None, ge=0)
    statement_closing_day: Optional[int] = Field(None, ge=1, le=31)
    payment_due_day: Optional[int] = Field(None, ge=1, le=31)
    color_hex: Optional[str] = Field(None, max_length=7)
    is_active: Optional[bool] = None


class CardResponse(CardBase):
    id: uuid.UUID
    user_id: uuid.UUID
    spent_this_period: Decimal
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CardDetailResponse(CardResponse):
    status: Dict[str, Any]

