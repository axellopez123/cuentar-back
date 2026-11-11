import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.card import Card
from app.models.enums import CardType, TransactionType
from app.models.transaction import Transaction
from app.models.user import User
from app.services.card_service import card_service
from app.utils.currency import quantize_currency
from app.utils.date_utils import calculate_billing_cycle


class DashboardService:
    async def get_dashboard_summary(
        self,
        session: AsyncSession,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Consolidates complete dashboard metrics:
        1. Cards summary (spent vs limits).
        2. Upcoming payment due dates sorted by proximity.
        3. Expense breakdown per participant (household member).
        4. Global financial totals.
        """
        ref_date = reference_date or date.today()

        # 1. Fetch active cards
        card_stmt = (
            select(Card)
            .where(Card.is_active.is_(True))
            .options(selectinload(Card.owner))
            .order_by(Card.alias.asc())
        )
        card_results = await session.execute(card_stmt)
        cards = list(card_results.scalars().all())

        cards_summary = []
        upcoming_payments = []
        total_credit_spent = Decimal("0.00")
        total_credit_limit = Decimal("0.00")
        total_debit_balance = Decimal("0.00")

        for card in cards:
            card_status = card_service.calculate_card_status(card, reference_date=ref_date)
            cards_summary.append(card_status)

            if card.card_type == CardType.CREDIT:
                total_credit_spent += card.spent_this_period
                total_credit_limit += card.credit_limit

                # If there's an amount to pay and cycle info exists, add to upcoming payments
                if card.spent_this_period > Decimal("0.00") and card_status.get("billing_cycle"):
                    cycle = card_status["billing_cycle"]
                    upcoming_payments.append({
                        "card_id": str(card.id),
                        "alias": card.alias,
                        "owner_name": card.owner.full_name if card.owner else "N/A",
                        "amount_to_pay": str(card.spent_this_period),
                        "payment_due_date": cycle["next_due_date"],
                        "days_until_due": cycle["days_until_due"],
                        "is_due_imminent": cycle["is_due_imminent"],
                    })
            elif card.card_type == CardType.DEBIT:
                total_debit_balance += card.current_balance

        # Sort upcoming payments chronologically (least days until due first)
        upcoming_payments.sort(key=lambda p: p["days_until_due"])

        # 2. Fetch users and calculate expense breakdown per member
        user_stmt = select(User).where(User.is_active.is_(True)).order_by(User.full_name.asc())
        user_results = await session.execute(user_stmt)
        users = list(user_results.scalars().all())

        # Start of current month as default period window
        month_start = datetime(ref_date.year, ref_date.month, 1, tzinfo=timezone.utc)

        participants_breakdown = []
        total_period_expenses = Decimal("0.00")

        for user in users:
            # Query expenses by user in current period
            tx_stmt = select(
                func.coalesce(func.sum(Transaction.amount), 0)
            ).where(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= month_start,
            )
            res = await session.execute(tx_stmt)
            user_spent = quantize_currency(Decimal(str(res.scalar() or 0)))

            # Shared expenses portion
            tx_shared_stmt = select(
                func.coalesce(func.sum(Transaction.amount), 0)
            ).where(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.is_shared.is_(True),
                Transaction.transaction_date >= month_start,
            )
            shared_res = await session.execute(tx_shared_stmt)
            shared_spent = quantize_currency(Decimal(str(shared_res.scalar() or 0)))

            total_period_expenses += user_spent

            participants_breakdown.append({
                "user_id": str(user.id),
                "full_name": user.full_name,
                "role": user.role.value,
                "total_spent": str(user_spent),
                "shared_spent": str(shared_spent),
                "personal_spent": str(quantize_currency(user_spent - shared_spent)),
            })

        # Add percentage of total expenses to participant breakdown
        for p in participants_breakdown:
            spent = Decimal(p["total_spent"])
            pct = (
                quantize_currency((spent / total_period_expenses) * Decimal("100.00"))
                if total_period_expenses > Decimal("0.00")
                else Decimal("0.00")
            )
            p["percentage_of_total"] = float(pct)

        return {
            "period_month": f"{ref_date.year}-{ref_date.month:02d}",
            "totals": {
                "total_credit_spent": str(quantize_currency(total_credit_spent)),
                "total_credit_limit": str(quantize_currency(total_credit_limit)),
                "total_debit_balance": str(quantize_currency(total_debit_balance)),
                "total_period_expenses": str(quantize_currency(total_period_expenses)),
            },
            "upcoming_payments": upcoming_payments,
            "participants_breakdown": participants_breakdown,
            "cards_summary": cards_summary,
        }


dashboard_service = DashboardService()

