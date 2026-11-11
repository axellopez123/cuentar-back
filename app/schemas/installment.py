import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class InstallmentPlanResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    card_id: uuid.UUID
    total_amount: Decimal
    monthly_amount: Decimal
    total_installments: int
    remaining_installments: int
    start_date: date
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

