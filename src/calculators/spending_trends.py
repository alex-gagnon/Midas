from collections import defaultdict

from ..models.transaction import Transaction

_EXCLUDE_CATEGORIES = {"income", "savings", "retirement"}


def calculate_spending_trends(
    transactions: list[Transaction],
    months: int = 6,
) -> dict:
    # Group expense transactions by (year, month)
    monthly: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for t in transactions:
        if t.amount >= 0 or t.category in _EXCLUDE_CATEGORIES:
            continue
        key = (t.date.year, t.date.month)
        monthly[key][t.category] += abs(t.amount)

    # Take the most recent N months present in data
    sorted_months = sorted(monthly.keys(), reverse=True)[:months]
    sorted_months.sort()  # chronological order for output

    trend = []
    for year, month in sorted_months:
        category_totals = monthly[(year, month)]
        total_spent = sum(category_totals.values())
        top_categories = sorted(
            [{"category": cat, "amount": round(amt, 2)} for cat, amt in category_totals.items()],
            key=lambda x: -x["amount"],
        )[:5]
        trend.append({
            "month": f"{year}-{month:02d}",
            "total_spent": round(total_spent, 2),
            "top_categories": top_categories,
        })

    return {
        "months_shown": len(trend),
        "trend": trend,
    }
