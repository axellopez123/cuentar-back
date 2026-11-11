import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CardType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transaction import Transaction


class Card(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cards"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    card_type: Mapped[CardType] = mapped_column(
        Enum(CardType, name="card_type_enum", native_enum=False),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    
    # Financial fields with strict precision
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    spent_this_period: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    monthly_budget_limit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    # Billing cycle days (1 - 31)
    statement_closing_day: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    payment_due_day: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    color_hex: Mapped[Optional[str]] = mapped_column(String(7), default="#2563EB", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="cards",
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="card",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} alias={self.alias} type={self.card_type}>"

