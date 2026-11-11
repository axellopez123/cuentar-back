import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.enums import TransactionType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.card import Card
    from app.models.category import Category
    from app.models.installment import InstallmentPlan
    from app.models.attachment import Attachment


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transactions"

    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type_enum", native_enum=False),
        default=TransactionType.EXPENSE,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Shared household finance attributes
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shared_split_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("50.00"),
        nullable=False,
    )

    # Months without interest (MSI) flag
    is_installment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="transactions")
    installment_plan: Mapped[Optional["InstallmentPlan"]] = relationship(
        "InstallmentPlan",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )
    attachments: Mapped[List["Attachment"]] = relationship(
        "Attachment",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} type={self.type} amount={self.amount}>"

