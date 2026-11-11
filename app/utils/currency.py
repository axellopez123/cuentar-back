from decimal import Decimal, ROUND_HALF_UP
from typing import Union

TWOPLACES = Decimal("0.01")


def to_decimal(value: Union[str, int, float, Decimal]) -> Decimal:
    """Converts a numeric value to Decimal safely without float precision leaks."""
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if isinstance(value, float):
        # Convert through str representation to avoid float binary approximation issues
        return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def quantize_currency(value: Decimal) -> Decimal:
    """Rounds a Decimal value to exactly 2 decimal places using ROUND_HALF_UP."""
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_monthly_installment(total_amount: Decimal, months: int) -> Decimal:
    """Calculates the monthly installment for MSI, rounding to 2 decimal places."""
    if months <= 0:
        raise ValueError("El número de meses debe ser mayor a cero.")
    return quantize_currency(total_amount / Decimal(months))

