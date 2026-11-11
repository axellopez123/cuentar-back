from datetime import date
from typing import Optional
from fastapi import APIRouter

from app.api.deps import SessionDep, CurrentUserDep
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard Financiero"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session: SessionDep,
    _current_user: CurrentUserDep,
    reference_date: Optional[date] = None,
):
    """
    Returns complete dashboard overview:
    - Total spent vs budget limits.
    - Upcoming payment due dates ordered by proximity.
    - Expense breakdown per participant.
    - Global totals.
    """
    summary = await dashboard_service.get_dashboard_summary(
        session=session,
        reference_date=reference_date,
    )
    return summary

