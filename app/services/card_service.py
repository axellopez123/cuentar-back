import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, BusinessRuleViolationException
from app.models.card import Card
from app.models.enums import CardType
from app.utils.currency import to_decimal, quantize_currency
from app.utils.date_utils import calculate_billing_cycle


class CardService:
    async def get_card_by_id(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
        with_owner: bool = False,
    ) -> Card:
        """Retrieves a card by ID or raises EntityNotFoundException."""
        stmt = select(Card).where(Card.id == card_id)
        if with_owner:
            stmt = stmt.options(selectinload(Card.owner))

        result = await session.execute(stmt)
        card = result.scalar_one_or_none()
        if not card:
            raise EntityNotFoundException("Tarjeta o Cuenta", card_id)
        return card

    async def list_cards(
        self,
        session: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        active_only: bool = True,
    ) -> List[Card]:
        """Lists all cards, optionally filtered by owner and active status."""
        stmt = select(Card).order_by(Card.created_at.desc())
        if user_id:
            stmt = stmt.where(Card.user_id == user_id)
        if active_only:
            stmt = stmt.where(Card.is_active.is_(True))

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create_card(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        alias: str,
        card_type: CardType,
        currency: str = "MXN",
        credit_limit: Decimal = Decimal("0.00"),
        current_balance: Decimal = Decimal("0.00"),
        monthly_budget_limit: Optional[Decimal] = None,
        statement_closing_day: Optional[int] = None,
        payment_due_day: Optional[int] = None,
        color_hex: Optional[str] = "#2563EB",
    ) -> Card:
        """Creates a new card/account validating day ranges and financial fields."""
        if statement_closing_day is not None and not (1 <= statement_closing_day <= 31):
            raise BusinessRuleViolationException(
                "El día de corte debe ser un número entre 1 y 31."
            )
        if payment_due_day is not None and not (1 <= payment_due_day <= 31):
            raise BusinessRuleViolationException(
                "El día límite de pago debe ser un número entre 1 y 31."
            )

        if card_type == CardType.CREDIT:
            if credit_limit < Decimal("0.00"):
                raise BusinessRuleViolationException(
                    "El límite de crédito no puede ser negativo."
                )
            # For a new credit card, available balance defaults to credit limit if not specified
            if current_balance == Decimal("0.00") and credit_limit > Decimal("0.00"):
                current_balance = credit_limit

        card = Card(
            user_id=user_id,
            alias=alias.strip(),
            card_type=card_type,
            currency=currency.upper(),
            credit_limit=quantize_currency(credit_limit),
            current_balance=quantize_currency(current_balance),
            spent_this_period=Decimal("0.00"),
            monthly_budget_limit=quantize_currency(monthly_budget_limit) if monthly_budget_limit else None,
            statement_closing_day=statement_closing_day,
            payment_due_day=payment_due_day,
            color_hex=color_hex,
            is_active=True,
        )
        session.add(card)
        await session.flush()
        return card

    def calculate_card_status(
        self,
        card: Card,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Calculates real-time metrics for a card:
        - Billing cycle (cut-off date, due date, days remaining).
        - Budget limit progress vs spent.
        - Credit available vs spent.
        """
        billing_info = None
        if card.card_type == CardType.CREDIT and card.statement_closing_day and card.payment_due_day:
            cycle = calculate_billing_cycle(
                card.statement_closing_day,
                card.payment_due_day,
                reference_date,
            )
            if cycle:
                billing_info = {
                    "next_closing_date": cycle.next_closing_date.isoformat(),
                    "days_until_closing": cycle.days_until_closing,
                    "next_due_date": cycle.next_due_date.isoformat(),
                    "days_until_due": cycle.days_until_due,
                    "is_due_imminent": cycle.is_due_imminent,
                }

        # Budget calculation
        budget_info = None
        if card.monthly_budget_limit and card.monthly_budget_limit > Decimal("0.00"):
            spent = card.spent_this_period
            limit = card.monthly_budget_limit
            pct = quantize_currency((spent / limit) * Decimal("100.00"))
            budget_info = {
                "monthly_budget_limit": str(limit),
                "spent_this_period": str(spent),
                "remaining_budget": str(max(Decimal("0.00"), limit - spent)),
                "usage_percentage": float(pct),
                "is_exceeded": spent > limit,
            }

        # Credit utilization
        credit_info = None
        if card.card_type == CardType.CREDIT:
            available = max(Decimal("0.00"), card.credit_limit - card.spent_this_period)
            utilization_pct = (
                quantize_currency((card.spent_this_period / card.credit_limit) * Decimal("100.00"))
                if card.credit_limit > Decimal("0.00")
                else Decimal("0.00")
            )
            credit_info = {
                "credit_limit": str(card.credit_limit),
                "spent_this_period": str(card.spent_this_period),
                "available_credit": str(available),
                "utilization_percentage": float(utilization_pct),
            }

        return {
            "card_id": str(card.id),
            "alias": card.alias,
            "card_type": card.card_type.value,
            "currency": card.currency,
            "current_balance": str(card.current_balance),
            "spent_this_period": str(card.spent_this_period),
            "billing_cycle": billing_info,
            "budget": budget_info,
            "credit": credit_info,
        }

    async def reset_period_spent(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
    ) -> Card:
        """Resets the spent amount for the period when a new billing cycle begins."""
        card = await self.get_card_by_id(session, card_id)
        card.spent_this_period = Decimal("0.00")
        await session.flush()
        return card


card_service = CardService()

