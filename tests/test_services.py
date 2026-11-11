import pytest
import pytest_asyncio
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.models.enums import UserRole, CardType, TransactionType
from app.models.user import User
from app.models.card import Card
from app.core.exceptions import (
    InsufficientFundsException,
    CreditLimitExceededException,
    InvalidFileException,
)
from app.utils.currency import to_decimal, quantize_currency, calculate_monthly_installment
from app.utils.date_utils import calculate_billing_cycle
from app.services.storage_service import StorageService
from app.services.card_service import CardService
from app.services.transaction_service import TransactionService
from app.services.dashboard_service import DashboardService


# 1. Currency & Mathematical Precision Tests
def test_currency_precision():
    assert to_decimal(0.1 + 0.2) == Decimal("0.30")
    assert quantize_currency(Decimal("100.555")) == Decimal("100.56")
    assert quantize_currency(Decimal("100.554")) == Decimal("100.55")


def test_msi_installment_calculation():
    total = Decimal("10000.00")
    months = 6
    installment = calculate_monthly_installment(total, months)
    assert installment == Decimal("1666.67")


# 2. Date & Billing Cycle Calculation Tests
def test_billing_cycle_dates():
    ref_date = date(2026, 11, 6)
    # Card with cut on 15th and due on 5th of next month
    cycle = calculate_billing_cycle(15, 5, ref_date)
    assert cycle is not None
    assert cycle.next_closing_date == date(2026, 11, 15)
    assert cycle.days_until_closing == 9
    assert cycle.next_due_date == date(2026, 12, 5)
    assert cycle.days_until_due == 29
    assert cycle.is_due_imminent is False

    # Card with cut on 28th and due on 18th
    cycle_2 = calculate_billing_cycle(28, 18, ref_date)
    assert cycle_2 is not None
    assert cycle_2.next_closing_date == date(2026, 11, 28)
    assert cycle_2.next_due_date == date(2026, 11, 18)
    assert cycle_2.days_until_due == 12


# 3. Storage Security & Magic Number Tests
@pytest.mark.asyncio
async def test_storage_validation_and_saving(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))

    # Empty file
    with pytest.raises(InvalidFileException):
        storage.validate_file("empty.png", b"")

    # Disallowed mime
    with pytest.raises(InvalidFileException):
        storage.validate_file("script.sh", b"#!/bin/bash\necho hello\n")

    # Valid PDF magic header
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    mime = storage.validate_file("recibo.pdf", pdf_bytes)
    assert mime == "application/pdf"

    # Save file securely
    saved_info = await storage.save_file("recibo_luz.pdf", pdf_bytes, subfolder="receipts")
    assert saved_info.original_name == "recibo_luz.pdf"
    assert saved_info.mime_type == "application/pdf"
    assert saved_info.relative_path.endswith(".pdf")

    # Verify physical file existence
    abs_path = storage.get_absolute_path(saved_info.relative_path)
    assert abs_path.exists()

    # Safely delete
    assert storage.delete_file(saved_info.relative_path) is True
    assert not abs_path.exists()


# 4. Async Service & State Invariant Tests
@pytest_asyncio.fixture
async def async_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_credit_card_and_transaction_flow(async_session: AsyncSession):
    card_svc = CardService()
    tx_svc = TransactionService()
    dash_svc = DashboardService()

    # Create primary user
    user = User(
        email="test@cuentar.com",
        hashed_password="fakehashsecret",
        full_name="Usuario Principal",
        role=UserRole.PRIMARY,
    )
    async_session.add(user)
    await async_session.flush()

    # Create credit card
    credit_card = await card_svc.create_card(
        session=async_session,
        user_id=user.id,
        alias="BBVA Platino",
        card_type=CardType.CREDIT,
        credit_limit=Decimal("50000.00"),
        monthly_budget_limit=Decimal("15000.00"),
        statement_closing_day=15,
        payment_due_day=5,
    )
    assert credit_card.spent_this_period == Decimal("0.00")
    assert credit_card.current_balance == Decimal("50000.00")

    # 1. Register normal expense
    tx1 = await tx_svc.create_expense(
        session=async_session,
        card_id=credit_card.id,
        user_id=user.id,
        amount=Decimal("3500.00"),
        description="Supermercado quincenal",
        is_shared=True,
    )
    assert tx1.amount == Decimal("3500.00")
    assert credit_card.spent_this_period == Decimal("3500.00")
    assert credit_card.current_balance == Decimal("46500.00")

    # 2. Register MSI purchase
    tx_msi = await tx_svc.create_expense(
        session=async_session,
        card_id=credit_card.id,
        user_id=user.id,
        amount=Decimal("12000.00"),
        description="Laptop a 6 MSI",
        is_installment=True,
        installment_months=6,
    )
    assert tx_msi.installment_plan is not None
    assert tx_msi.installment_plan.monthly_amount == Decimal("2000.00")
    assert tx_msi.installment_plan.remaining_installments == 6
    assert credit_card.spent_this_period == Decimal("15500.00")

    # 3. Test credit limit violation
    with pytest.raises(CreditLimitExceededException):
        await tx_svc.create_expense(
            session=async_session,
            card_id=credit_card.id,
            user_id=user.id,
            amount=Decimal("40000.00"),
            description="Excede límite",
        )

    # 4. Register payment to credit card
    payment_tx = await tx_svc.create_payment(
        session=async_session,
        card_id=credit_card.id,
        user_id=user.id,
        amount=Decimal("5500.00"),
        description="Abono a tarjeta",
    )
    assert payment_tx.type == TransactionType.PAYMENT
    assert credit_card.spent_this_period == Decimal("10000.00")
    assert credit_card.current_balance == Decimal("40000.00")

    # 5. Dashboard summary check
    summary = await dash_svc.get_dashboard_summary(async_session, reference_date=date(2026, 11, 6))
    assert len(summary["upcoming_payments"]) == 1
    payment_item = summary["upcoming_payments"][0]
    assert payment_item["alias"] == "BBVA Platino"
    assert payment_item["amount_to_pay"] == "10000.00"
    assert payment_item["days_until_due"] == 29
    assert len(summary["participants_breakdown"]) == 1
    assert summary["participants_breakdown"][0]["total_spent"] == "15500.00"


@pytest.mark.asyncio
async def test_debit_card_flow(async_session: AsyncSession):
    card_svc = CardService()
    tx_svc = TransactionService()

    user = User(
        email="partner@cuentar.com",
        hashed_password="fakehashsecret",
        full_name="Mi Pareja",
        role=UserRole.PARTNER,
    )
    async_session.add(user)
    await async_session.flush()

    # Create debit card with initial balance of 5000
    debit_card = await card_svc.create_card(
        session=async_session,
        user_id=user.id,
        alias="Nu Débito",
        card_type=CardType.DEBIT,
        current_balance=Decimal("5000.00"),
    )
    assert debit_card.current_balance == Decimal("5000.00")

    # Purchase with sufficient funds
    tx_debit = await tx_svc.create_expense(
        session=async_session,
        card_id=debit_card.id,
        user_id=user.id,
        amount=Decimal("1500.00"),
        description="Pago servicios internet",
    )
    assert debit_card.current_balance == Decimal("3500.00")
    assert debit_card.spent_this_period == Decimal("1500.00")

    # Purchase with insufficient funds should fail
    with pytest.raises(InsufficientFundsException):
        await tx_svc.create_expense(
            session=async_session,
            card_id=debit_card.id,
            user_id=user.id,
            amount=Decimal("4000.00"),
            description="Compra excesiva",
        )

    # Deposit / Payment to debit
    deposit_tx = await tx_svc.create_payment(
        session=async_session,
        card_id=debit_card.id,
        user_id=user.id,
        amount=Decimal("2000.00"),
        description="Transferencia / Depósito",
    )
    assert debit_card.current_balance == Decimal("5500.00")
