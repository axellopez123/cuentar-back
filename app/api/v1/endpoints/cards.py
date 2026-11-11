import uuid
from typing import List, Optional
from fastapi import APIRouter, status

from app.api.deps import SessionDep, CurrentUserDep
from app.schemas.card import CardCreate, CardUpdate, CardResponse, CardDetailResponse
from app.services.card_service import card_service

router = APIRouter(prefix="/cards", tags=["Cuentas y Tarjetas"])


@router.get("", response_model=List[CardResponse])
async def list_cards(
    session: SessionDep,
    _current_user: CurrentUserDep,
    user_id: Optional[uuid.UUID] = None,
    active_only: bool = True,
):
    """Lists cards/accounts with optional user filtering."""
    return await card_service.list_cards(session, user_id=user_id, active_only=active_only)


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    card_in: CardCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Creates a new debit or credit card account."""
    owner_id = card_in.user_id or current_user.id
    card = await card_service.create_card(
        session=session,
        user_id=owner_id,
        alias=card_in.alias,
        card_type=card_in.card_type,
        currency=card_in.currency,
        credit_limit=card_in.credit_limit,
        current_balance=card_in.current_balance,
        monthly_budget_limit=card_in.monthly_budget_limit,
        statement_closing_day=card_in.statement_closing_day,
        payment_due_day=card_in.payment_due_day,
        color_hex=card_in.color_hex,
    )
    await session.commit()
    await session.refresh(card)
    return card


@router.get("/{card_id}", response_model=CardDetailResponse)
async def get_card_details(
    card_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Retrieves a card including real-time cycle status, budget progress, and limits."""
    card = await card_service.get_card_by_id(session, card_id)
    status_metrics = card_service.calculate_card_status(card)
    
    return CardDetailResponse(
        id=card.id,
        user_id=card.user_id,
        alias=card.alias,
        card_type=card.card_type,
        currency=card.currency,
        credit_limit=card.credit_limit,
        current_balance=card.current_balance,
        spent_this_period=card.spent_this_period,
        monthly_budget_limit=card.monthly_budget_limit,
        statement_closing_day=card.statement_closing_day,
        payment_due_day=card.payment_due_day,
        color_hex=card.color_hex,
        is_active=card.is_active,
        created_at=card.created_at,
        status=status_metrics,
    )


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: uuid.UUID,
    card_in: CardUpdate,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Updates card metadata, limits, and billing cycle days."""
    card = await card_service.get_card_by_id(session, card_id)

    if card_in.alias is not None:
        card.alias = card_in.alias.strip()
    if card_in.credit_limit is not None:
        card.credit_limit = card_in.credit_limit
    if card_in.monthly_budget_limit is not None:
        card.monthly_budget_limit = card_in.monthly_budget_limit
    if card_in.statement_closing_day is not None:
        card.statement_closing_day = card_in.statement_closing_day
    if card_in.payment_due_day is not None:
        card.payment_due_day = card_in.payment_due_day
    if card_in.color_hex is not None:
        card.color_hex = card_in.color_hex
    if card_in.is_active is not None:
        card.is_active = card_in.is_active

    await session.commit()
    await session.refresh(card)
    return card


@router.post("/{card_id}/reset-period", response_model=CardResponse)
async def reset_card_billing_period(
    card_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Resets the spent amount for the period when a new billing cycle begins."""
    card = await card_service.reset_period_spent(session, card_id)
    await session.commit()
    await session.refresh(card)
    return card

