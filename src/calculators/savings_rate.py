from datetime import date

from ..models.transaction import Transaction

_SAVINGS_CATEGORIES = {"savings", "retirement"}


def calculate_savings_rate(
    transactions: list[Transaction],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    def in_range(t: Transaction) -> bool:
        if start_date and t.date < start_date:
            return False
        if end_date and t.date > end_date:
            return False
        return True

    in_period = [t for t in transactions if in_range(t)]

    total_income = sum(
        t.amount for t in in_period if t.category == "income" and t.amount > 0
    )

    breakdown: dict[str, float] = {}
    for t in in_period:
        if t.category in _SAVINGS_CATEGORIES:
            breakdown[t.category] = breakdown.get(t.category, 0.0) + abs(t.amount)

    total_saved = sum(breakdown.values())
    savings_rate_pct = round(total_saved / total_income * 100, 1) if total_income > 0 else 0.0

    return {
        "period": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
        },
        "income": round(total_income, 2),
        "total_saved": round(total_saved, 2),
        "savings_rate_pct": savings_rate_pct,
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
    }
