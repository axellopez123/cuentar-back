from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for application errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} con id '{entity_id}' no fue encontrado.",
            status_code=404,
            details={"entity": entity_name, "id": str(entity_id)},
        )


class InsufficientFundsException(AppException):
    def __init__(self, current_balance: str, required_amount: str):
        super().__init__(
            message="Saldo insuficiente en la cuenta de débito para realizar la transacción.",
            status_code=422,
            details={
                "current_balance": current_balance,
                "required_amount": required_amount,
            },
        )


class CreditLimitExceededException(AppException):
    def __init__(self, available_credit: str, required_amount: str):
        super().__init__(
            message="La transacción excede la línea de crédito disponible.",
            status_code=422,
            details={
                "available_credit": available_credit,
                "required_amount": required_amount,
            },
        )


class InvalidFileException(AppException):
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Archivo no válido: {reason}",
            status_code=400,
            details=details,
        )


class BusinessRuleViolationException(AppException):
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Regla de negocio no satisfecha: {reason}",
            status_code=422,
            details=details,
        )

