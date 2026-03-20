import calendar
from datetime import date

from ..models.transaction import Transaction
from .budget_models import DEFAULT_MODEL, MODELS, BudgetModel


def _classify(category: str, model: BudgetModel) -> str:
    cat = category.lower().strip()
    for bucket in model.buckets:
        if cat in bucket.categories:
            return bucket.name
    return model.default_bucket


def _on_track(actual_pct: float, target_pct: float, direction: str) -> bool:
    if direction == "lte":
        return actual_pct <= target_pct
    if direction == "gte":
        return actual_pct >= target_pct
    return True


def calculate_budget_breakdown(
    transactions: list[Transaction],
    start_date: date | None = None,
    end_date: date | None = None,
    model_key: str = DEFAULT_MODEL,
) -> dict:
    if model_key not in MODELS:
        raise ValueError(f"Unknown budget model '{model_key}'. Available: {list(MODELS)}")

    model = MODELS[model_key]

    def in_range(t: Transaction) -> bool:
        if start_date and t.date < start_date:
            return False
        if end_date and t.date > end_date:
            return False
        return True

    in_period = [t for t in transactions if in_range(t)]
    total_income = sum(t.amount for t in in_period if t.category == "income" and t.amount > 0)

    def pct(amount: float) -> float:
        return round(amount / total_income * 100, 1) if total_income > 0 else 0.0

    period = {
        "start": start_date.isoformat() if start_date else None,
        "end": end_date.isoformat() if end_date else None,
    }

    # --- Zero-based: each category is its own line item ---
    if model.key == "zero_based":
        categories: dict[str, float] = {}
        for t in in_period:
            if t.category == "income" or t.amount >= 0:
                continue
            spent = abs(t.amount)
            categories[t.category] = categories.get(t.category, 0.0) + spent

        total_expenses = sum(categories.values())
        remaining = total_income - total_expenses
        line_items = [
            {
                "category": cat,
                "amount": round(amt, 2),
                "pct_of_income": pct(amt),
                "over_budget": pct(amt) > 15.0,
            }
            for cat, amt in sorted(categories.items(), key=lambda x: -x[1])
        ]
        return {
            "model": {"key": model.key, "name": model.name},
            "period": period,
            "income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "remaining": round(remaining, 2),
            "on_track": abs(remaining) < 1.0,  # within $1 of zero
            "line_items": line_items,
        }

    # --- Percentage-based models ---
    bucket_totals: dict[str, float] = {b.name: 0.0 for b in model.buckets}
    bucket_detail: dict[str, dict[str, float]] = {b.name: {} for b in model.buckets}

    for t in in_period:
        if t.category == "income" or t.amount >= 0:
            continue
        bucket_name = _classify(t.category, model)
        if bucket_name not in bucket_totals:
            bucket_totals[bucket_name] = 0.0
            bucket_detail[bucket_name] = {}
        spent = abs(t.amount)
        bucket_totals[bucket_name] += spent
        bucket_detail[bucket_name][t.category] = (
            bucket_detail[bucket_name].get(t.category, 0.0) + spent
        )

    total_expenses = sum(bucket_totals.values())

    breakdown = {}
    for bucket in model.buckets:
        amount = bucket_totals[bucket.name]
        actual_pct = pct(amount)
        entry = {
            "label": bucket.label,
            "amount": round(amount, 2),
            "actual_pct": actual_pct,
            "target_pct": bucket.target_pct,
            "categories": {
                k: round(v, 2)
                for k, v in sorted(bucket_detail[bucket.name].items(), key=lambda x: -x[1])
            },
        }
        if bucket.on_track_direction and bucket.target_pct is not None:
            entry["on_track"] = _on_track(actual_pct, bucket.target_pct, bucket.on_track_direction)
        breakdown[bucket.name] = entry

    return {
        "model": {"key": model.key, "name": model.name, "description": model.description},
        "period": period,
        "income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "remaining": round(total_income - total_expenses, 2),
        "breakdown": breakdown,
    }


def calculate_monthly_budget_breakdown(
    transactions: list[Transaction],
    start_date: date | None = None,
    end_date: date | None = None,
    model_key: str = DEFAULT_MODEL,
) -> dict:
    """Return a budget breakdown split month-by-month over the given date range.

    If start_date / end_date are omitted, defaults to the current calendar month.
    Raises ValueError if start_date > end_date or if model_key is unknown.
    """
    if model_key not in MODELS:
        raise ValueError(f"Unknown budget model '{model_key}'. Available: {list(MODELS)}")

    today = date.today()
    if start_date is None:
        start_date = date(today.year, today.month, 1)
    if end_date is None:
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)

    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})"
        )

    # Build (year, month) tuples spanning the full range
    months: list[tuple[int, int]] = []
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1

    model = MODELS[model_key]
    month_entries = []
    for year, month in months:
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        entry = calculate_budget_breakdown(transactions, month_start, month_end, model_key)
        entry["month"] = f"{year}-{month:02d}"
        entry.pop("model", None)
        month_entries.append(entry)

    return {
        "model": {"key": model.key, "name": model.name, "description": model.description},
        "months_count": len(month_entries),
        "months": month_entries,
    }


def list_budget_models() -> list[dict]:
    return [{"key": m.key, "name": m.name, "description": m.description} for m in MODELS.values()]
