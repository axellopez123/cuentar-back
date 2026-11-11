from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class UpcomingPaymentItem(BaseModel):
    card_id: str
    alias: str
    owner_name: str
    amount_to_pay: str
    payment_due_date: str
    days_until_due: int
    is_due_imminent: bool


class ParticipantBreakdownItem(BaseModel):
    user_id: str
    full_name: str
    role: str
    total_spent: str
    shared_spent: str
    personal_spent: str
    percentage_of_total: float


class DashboardTotals(BaseModel):
    total_credit_spent: str
    total_credit_limit: str
    total_debit_balance: str
    total_period_expenses: str


class DashboardResponse(BaseModel):
    period_month: str
    totals: DashboardTotals
    upcoming_payments: List[UpcomingPaymentItem]
    participants_breakdown: List[ParticipantBreakdownItem]
    cards_summary: List[Dict[str, Any]]

