import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TransactionType
from app.schemas.attachment import AttachmentResponse
from app.schemas.installment import InstallmentPlanResponse


class TransactionBase(BaseModel):
    card_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=255)
    transaction_date: Optional[datetime] = None


class TransactionCreateExpense(TransactionBase):
    user_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    is_shared: bool = False
    shared_split_ratio: Decimal = Field(default=Decimal("50.00"), ge=0, le=100)
    is_installment: bool = False
    installment_months: Optional[int] = Field(None, ge=2, le=48)


class TransactionCreatePayment(BaseModel):
    card_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0)
    description: str = Field(default="Pago a tarjeta", min_length=1, max_length=255)
    transaction_date: Optional[datetime] = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    card_id: uuid.UUID
    user_id: uuid.UUID
    category_id: Optional[uuid.UUID]
    type: TransactionType
    amount: Decimal
    description: str
    transaction_date: datetime
    is_shared: bool
    shared_split_ratio: Decimal
    is_installment: bool
    created_at: datetime

    card_alias: Optional[str] = None
    user_name: Optional[str] = None
    category_name: Optional[str] = None

    installment_plan: Optional[InstallmentPlanResponse] = None
    attachments: List[AttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)

