"""Pure schedule math (no DB). Decimal only; the last installment absorbs the rounding remainder."""
import calendar
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

from apps.common.exceptions import ValidationFailed
from apps.common.money import TWO_PLACES


def add_months(anchor: date, months: int) -> date:
    """anchor + N months, clamped to month end (31 Jan + 1 month = 28/29 Feb). Always computed from the anchor."""
    index = anchor.month - 1 + months
    year, month = anchor.year + index // 12, index % 12 + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def due_date(start: date, frequency: str, n: int) -> date:
    """n-th installment (1-based) falls due n periods after start_date [assumption]."""
    if frequency == "DAILY":
        return start + timedelta(days=n)
    if frequency == "WEEKLY":
        return start + timedelta(weeks=n)
    if frequency == "MONTHLY":
        return add_months(start, n)
    if frequency == "QUARTERLY":
        return add_months(start, 3 * n)
    if frequency == "HALF_YEARLY":
        return add_months(start, 6 * n)
    raise ValueError(f"unknown frequency {frequency}")


def build_schedule(total_payable: Decimal, count: int, frequency: str, start: date) -> list[tuple[int, date, Decimal]]:
    base = (total_payable / count).quantize(TWO_PLACES, rounding=ROUND_DOWN)
    if base < TWO_PLACES:
        raise ValidationFailed("Total payable is too small for this number of installments.",
                               details={"fields": {"installment_count": ["Too many installments for the amount."]}})
    amounts = [base] * (count - 1) + [total_payable - base * (count - 1)]
    assert sum(amounts) == total_payable
    return [(i, due_date(start, frequency, i), amounts[i - 1]) for i in range(1, count + 1)]
