import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import SessionDep, CurrentUserDep
from app.models.enums import TransactionType
from app.models.transaction import Transaction
from app.schemas.attachment import AttachmentResponse
from app.schemas.transaction import (
    TransactionCreateExpense,
    TransactionCreatePayment,
    TransactionResponse,
)
from app.services.storage_service import storage_service, SavedFileInfo
from app.services.transaction_service import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transacciones"])


def serialize_transaction(tx: Transaction) -> TransactionResponse:
    """Helper to convert ORM Transaction into TransactionResponse with relation names."""
    return TransactionResponse(
        id=tx.id,
        card_id=tx.card_id,
        user_id=tx.user_id,
        category_id=tx.category_id,
        type=tx.type,
        amount=tx.amount,
        description=tx.description,
        transaction_date=tx.transaction_date,
        is_shared=tx.is_shared,
        shared_split_ratio=tx.shared_split_ratio,
        is_installment=tx.is_installment,
        created_at=tx.created_at,
        card_alias=tx.card.alias if tx.card else None,
        user_name=tx.user.full_name if tx.user else None,
        category_name=tx.category.name if tx.category else None,
        installment_plan=tx.installment_plan,
        attachments=tx.attachments,
    )


@router.get("", response_model=List[TransactionResponse])
async def list_transactions(
    session: SessionDep,
    _current_user: CurrentUserDep,
    card_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    transaction_type: Optional[TransactionType] = None,
    is_shared: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Lists transactions with rich filtering and relationships loaded."""
    txs = await transaction_service.list_transactions(
        session=session,
        card_id=card_id,
        user_id=user_id,
        category_id=category_id,
        transaction_type=transaction_type,
        is_shared=is_shared,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [serialize_transaction(tx) for tx in txs]


@router.post("/expense", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_in: TransactionCreateExpense,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Registers an expense (with support for MSI and shared household ratio)."""
    responsible_user_id = expense_in.user_id or current_user.id
    tx = await transaction_service.create_expense(
        session=session,
        card_id=expense_in.card_id,
        user_id=responsible_user_id,
        amount=expense_in.amount,
        description=expense_in.description,
        category_id=expense_in.category_id,
        transaction_date=expense_in.transaction_date,
        is_shared=expense_in.is_shared,
        shared_split_ratio=expense_in.shared_split_ratio,
        is_installment=expense_in.is_installment,
        installment_months=expense_in.installment_months,
    )
    await session.commit()
    # Re-fetch with loaded relations
    full_tx = await transaction_service.get_transaction_by_id(session, tx.id)
    return serialize_transaction(full_tx)


@router.post("/payment", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_in: TransactionCreatePayment,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Registers a payment or abono to a credit card, restoring available balance."""
    responsible_user_id = payment_in.user_id or current_user.id
    tx = await transaction_service.create_payment(
        session=session,
        card_id=payment_in.card_id,
        user_id=responsible_user_id,
        amount=payment_in.amount,
        description=payment_in.description,
        transaction_date=payment_in.transaction_date,
    )
    await session.commit()
    full_tx = await transaction_service.get_transaction_by_id(session, tx.id)
    return serialize_transaction(full_tx)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Retrieves a single transaction by ID."""
    tx = await transaction_service.get_transaction_by_id(session, transaction_id)
    return serialize_transaction(tx)


@router.post("/{transaction_id}/attachments", response_model=List[AttachmentResponse])
async def upload_transaction_attachments(
    transaction_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUserDep,
    files: List[UploadFile] = File(...),
):
    """Uploads and associates evidence files (photos, tickets, receipts, PDFs) to a transaction."""
    from app.models.attachment import Attachment

    tx = await transaction_service.get_transaction_by_id(session, transaction_id)
    saved_attachments = []

    for file in files:
        content = await file.read()
        saved_info: SavedFileInfo = await storage_service.save_file(
            original_filename=file.filename or "comprobante.pdf",
            content=content,
            subfolder="receipts",
        )
        attachment = Attachment(
            transaction_id=tx.id,
            file_name=saved_info.original_name,
            file_path=saved_info.relative_path,
            mime_type=saved_info.mime_type,
            file_size_bytes=saved_info.file_size_bytes,
        )
        session.add(attachment)
        saved_attachments.append(attachment)

    await session.commit()
    for att in saved_attachments:
        await session.refresh(att)

    return saved_attachments

