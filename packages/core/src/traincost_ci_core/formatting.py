"""Consistent display of monetary values without changing the numeric inputs."""

from decimal import Decimal


def format_money(value: float) -> str:
    amount = Decimal(str(value))
    if amount != 0 and abs(amount) < Decimal("0.01"):
        return f"${amount:,.{max(2, -amount.as_tuple().exponent)}f}"
    return f"${amount:,.2f}"


def format_money_pair(first: float, second: float) -> tuple[str, str]:
    """Disambiguate unequal comparisons that would round to the same amount."""
    left, right = format_money(first), format_money(second)
    if first != second and left == right:
        digits = max(2, -Decimal(str(first)).as_tuple().exponent,
                     -Decimal(str(second)).as_tuple().exponent)
        left = f"${Decimal(str(first)):,.{digits}f}"
        right = f"${Decimal(str(second)):,.{digits}f}"
    return left, right
