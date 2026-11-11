import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass(frozen=True)
class BillingCycleInfo:
    next_closing_date: date
    days_until_closing: int
    next_due_date: date
    days_until_due: int
    is_due_imminent: bool  # True if <= 5 days remaining


def get_clamped_date(year: int, month: int, day: int) -> date:
    """Returns a valid date object, clamping day to month's maximum days if necessary."""
    max_days = calendar.monthrange(year, month)[1]
    safe_day = min(day, max_days)
    return date(year, month, safe_day)


def add_months(d: date, months: int) -> date:
    """Adds or subtracts months to a date, preserving day if possible or clamping."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return get_clamped_date(year, month, d.day)


def calculate_billing_cycle(
    statement_closing_day: Optional[int],
    payment_due_day: Optional[int],
    reference_date: Optional[date] = None,
) -> Optional[BillingCycleInfo]:
    """
    Calculates next closing date and next payment due date with days remaining.
    Returns None if days are not configured (e.g. for debit accounts).
    """
    if not statement_closing_day or not payment_due_day:
        return None

    today = reference_date or date.today()

    # 1. Determine next closing date
    closing_this_month = get_clamped_date(today.year, today.month, statement_closing_day)
    if today <= closing_this_month:
        next_closing_date = closing_this_month
    else:
        next_month_ref = add_months(today, 1)
        next_closing_date = get_clamped_date(
            next_month_ref.year, next_month_ref.month, statement_closing_day
        )

    days_until_closing = (next_closing_date - today).days

    # 2. Determine payment due date for the statement closing cycle
    # If due_day <= closing_day, payment is in the month following the closing date.
    # Otherwise, it's in the same month.
    if payment_due_day <= statement_closing_day:
        due_month_ref = add_months(next_closing_date, 1)
        cycle_due_date = get_clamped_date(
            due_month_ref.year, due_month_ref.month, payment_due_day
        )
    else:
        cycle_due_date = get_clamped_date(
            next_closing_date.year, next_closing_date.month, payment_due_day
        )

    # 3. Determine the immediate payment due date (could be for statement that just closed)
    # Check the closing date that occurred right before or on today
    if today > closing_this_month:
        last_closing_date = closing_this_month
    else:
        last_month_ref = add_months(today, -1)
        last_closing_date = get_clamped_date(
            last_month_ref.year, last_month_ref.month, statement_closing_day
        )

    # Corresponding due date for the last closed statement
    if payment_due_day <= statement_closing_day:
        immediate_due_month_ref = add_months(last_closing_date, 1)
        immediate_due_date = get_clamped_date(
            immediate_due_month_ref.year, immediate_due_month_ref.month, payment_due_day
        )
    else:
        immediate_due_date = get_clamped_date(
            last_closing_date.year, last_closing_date.month, payment_due_day
        )

    # If the immediate due date has not passed yet, that is the most urgent payment!
    # If it already passed, the next payment due is the one from the upcoming statement.
    if today <= immediate_due_date:
        next_due_date = immediate_due_date
    else:
        next_due_date = cycle_due_date

    days_until_due = (next_due_date - today).days

    return BillingCycleInfo(
        next_closing_date=next_closing_date,
        days_until_closing=max(0, days_until_closing),
        next_due_date=next_due_date,
        days_until_due=days_until_due,
        is_due_imminent=0 <= days_until_due <= 5,
    )

