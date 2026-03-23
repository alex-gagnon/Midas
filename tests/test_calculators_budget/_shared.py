"""Shared helpers and fixtures for budget calculator tests."""

from datetime import date

from src.models.transaction import Transaction


def _txn(d, amount, category, account_id="chk_001", description=""):
    return Transaction(
        date=date.fromisoformat(d),
        amount=amount,
        description=description or category,
        category=category,
        account_id=account_id,
    )


# Standard fixture for most tests: 7000 income, clear expenses
# income=7000, needs=1800+200=2000(housing+groceries), wants=100+50=150(dining+shopping),
# savings=500+200=700(retirement+savings)
STANDARD_TRANSACTIONS = [
    _txn("2026-03-01", 3_500.00, "income"),
    _txn("2026-03-15", 3_500.00, "income"),
    _txn("2026-03-01", -1_800.00, "housing"),
    _txn("2026-03-03", -200.00, "groceries"),
    _txn("2026-03-07", -100.00, "dining"),
    _txn("2026-03-10", -50.00, "shopping"),
    _txn("2026-03-14", -500.00, "retirement"),
    _txn("2026-03-15", -200.00, "savings"),
]
