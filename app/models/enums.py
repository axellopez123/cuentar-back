from enum import Enum


class UserRole(str, Enum):
    PRIMARY = "primary"
    PARTNER = "partner"
    MEMBER = "member"


class CardType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionType(str, Enum):
    EXPENSE = "expense"
    PAYMENT = "payment"
    ADJUSTMENT = "adjustment"

