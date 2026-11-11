import uuid
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class Attachment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attachments"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="attachments",
    )

    def __repr__(self) -> str:
        return f"<Attachment id={self.id} file={self.file_name}>"

