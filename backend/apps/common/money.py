"""Money helpers. Never use float for money; always Decimal quantized to 2 places."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    if isinstance(value, float):
        raise TypeError("float is not allowed for money; pass str or Decimal")
    try:
        return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc
