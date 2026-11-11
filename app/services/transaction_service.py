import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    EntityNotFoundException,
    InsufficientFundsException,
    CreditLimitExceededException,
    BusinessRuleViolationException,
)
from app.models.attachment import Attachment
from app.models.card import Card
from app.models.enums import CardType, TransactionType
from app.models.installment import InstallmentPlan
from app.models.transaction import Transaction
from app.models.user import User
from app.services.card_service import card_service
from app.services.storage_service import storage_service, SavedFileInfo
from app.utils.currency import to_decimal, quantize_currency, calculate_monthly_installment


class TransactionService:
    async def get_transaction_by_id(
        self,
        session: AsyncSession,
        transaction_id: uuid.UUID,
    ) -> Transaction:
        """Retrieves a transaction with all related entities loaded."""
        stmt = (
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(
                selectinload(Transaction.card),
                selectinload(Transaction.user),
                selectinload(Transaction.category),
                selectinload(Transaction.installment_plan),
                selectinload(Transaction.attachments),
            )
        )
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()
        if not tx:
            raise EntityNotFoundException("Transacción", transaction_id)
        return tx

    async def list_transactions(
        self,
        session: AsyncSession,
        card_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[TransactionType] = None,
        is_shared: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Transaction]:
        """Queries transactions with comprehensive filters and eager loading."""
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.card),
                selectinload(Transaction.user),
                selectinload(Transaction.category),
                selectinload(Transaction.installment_plan),
                selectinload(Transaction.attachments),
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        )

        if card_id:
            stmt = stmt.where(Transaction.card_id == card_id)
        if user_id:
            stmt = stmt.where(Transaction.user_id == user_id)
        if category_id:
            stmt = stmt.where(Transaction.category_id == category_id)
        if transaction_type:
            stmt = stmt.where(Transaction.type == transaction_type)
        if is_shared is not None:
            stmt = stmt.where(Transaction.is_shared == is_shared)
        if start_date:
            stmt = stmt.where(Transaction.transaction_date >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.transaction_date <= end_date)

        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create_expense(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
        user_id: uuid.UUID,
        amount: Decimal,
        description: str,
        category_id: Optional[uuid.UUID] = None,
        transaction_date: Optional[datetime] = None,
        is_shared: bool = False,
        shared_split_ratio: Decimal = Decimal("50.00"),
        is_installment: bool = False,
        installment_months: Optional[int] = None,
        attached_files: Optional[List[SavedFileInfo]] = None,
    ) -> Transaction:
        """
        Registers an expense, validating limits, adjusting card balances atomically,
        handling MSI (Meses Sin Intereses), and linking uploaded files.
        """
        amount = quantize_currency(amount)
        if amount <= Decimal("0.00"):
            raise BusinessRuleViolationException("El monto del gasto debe ser mayor a cero.")

        card = await card_service.get_card_by_id(session, card_id)
        if not card.is_active:
            raise BusinessRuleViolationException(f"La tarjeta '{card.alias}' está inactiva.")

        # Balance & Limit updates according to card type
        if card.card_type == CardType.DEBIT:
            if card.current_balance < amount:
                raise InsufficientFundsException(
                    current_balance=str(card.current_balance),
                    required_amount=str(amount),
                )
            card.current_balance = quantize_currency(card.current_balance - amount)
            card.spent_this_period = quantize_currency(card.spent_this_period + amount)

        elif card.card_type == CardType.CREDIT:
            available_credit = card.credit_limit - card.spent_this_period
            if card.credit_limit > Decimal("0.00") and amount > available_credit:
                raise CreditLimitExceededException(
                    available_credit=str(available_credit),
                    required_amount=str(amount),
                )
            card.spent_this_period = quantize_currency(card.spent_this_period + amount)
            card.current_balance = quantize_currency(
                max(Decimal("0.00"), card.credit_limit - card.spent_this_period)
            )

        tx_date = transaction_date or datetime.now(timezone.utc)

        # Validate MSI parameters
        if is_installment:
            if not installment_months or installment_months < 2:
                raise BusinessRuleViolationException(
                    "Para compras a meses sin intereses, el plazo debe ser de al menos 2 meses."
                )

        transaction = Transaction(
            card_id=card.id,
            user_id=user_id,
            category_id=category_id,
            type=TransactionType.EXPENSE,
            amount=amount,
            description=description.strip(),
            transaction_date=tx_date,
            is_shared=is_shared,
            shared_split_ratio=quantize_currency(shared_split_ratio),
            is_installment=is_installment,
        )
        session.add(transaction)
        await session.flush()

        # Create installment plan if applicable
        if is_installment and installment_months:
            monthly_amount = calculate_monthly_installment(amount, installment_months)
            installment_plan = InstallmentPlan(
                transaction_id=transaction.id,
                card_id=card.id,
                total_amount=amount,
                monthly_amount=monthly_amount,
                total_installments=installment_months,
                remaining_installments=installment_months,
                start_date=tx_date.date(),
                is_active=True,
            )
            session.add(installment_plan)

        # Attach saved files
        if attached_files:
            for file_info in attached_files:
                attachment = Attachment(
                    transaction_id=transaction.id,
                    file_name=file_info.original_name,
                    file_path=file_info.relative_path,
                    mime_type=file_info.mime_type,
                    file_size_bytes=file_info.file_size_bytes,
                )
                session.add(attachment)

        await session.flush()
        return await self.get_transaction_by_id(session, transaction.id)

    async def create_payment(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
        user_id: uuid.UUID,
        amount: Decimal,
        description: str = "Pago a tarjeta",
        transaction_date: Optional[datetime] = None,
        attached_files: Optional[List[SavedFileInfo]] = None,
    ) -> Transaction:
        """
        Registers a payment/abono to a card:
        - Reduces spent_this_period.
        - Restores available credit balance.
        """
        amount = quantize_currency(amount)
        if amount <= Decimal("0.00"):
            raise BusinessRuleViolationException("El monto del abono o pago debe ser mayor a cero.")

        card = await card_service.get_card_by_id(session, card_id)

        if card.card_type == CardType.CREDIT:
            # Reduce spent amount
            card.spent_this_period = quantize_currency(
                max(Decimal("0.00"), card.spent_this_period - amount)
            )
            # Restore available balance up to credit limit
            card.current_balance = quantize_currency(
                min(card.credit_limit, card.credit_limit - card.spent_this_period)
            )
        elif card.card_type == CardType.DEBIT:
            # For debit, payment is a balance replenishment / deposit
            card.current_balance = quantize_currency(card.current_balance + amount)

        tx_date = transaction_date or datetime.now(timezone.utc)

        transaction = Transaction(
            card_id=card.id,
            user_id=user_id,
            category_id=None,
            type=TransactionType.PAYMENT,
            amount=amount,
            description=description.strip(),
            transaction_date=tx_date,
            is_shared=False,
            shared_split_ratio=Decimal("0.00"),
            is_installment=False,
        )
        session.add(transaction)
        await session.flush()

        if attached_files:
            for file_info in attached_files:
                attachment = Attachment(
                    transaction_id=transaction.id,
                    file_name=file_info.original_name,
                    file_path=file_info.relative_path,
                    mime_type=file_info.mime_type,
                    file_size_bytes=file_info.file_size_bytes,
                )
                session.add(attachment)

        await session.flush()
        return await self.get_transaction_by_id(session, transaction.id)


transaction_service = TransactionService()

