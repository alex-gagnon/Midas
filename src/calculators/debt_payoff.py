"""Debt payoff projection calculator using the avalanche method.

Schema note: accounts.csv has no APR/interest-rate column, so all debts are
assigned a hardcoded default APR of 20 % (a common credit-card benchmark).
True avalanche ordering (highest rate first) is therefore not distinguishable
by rate; instead, debts are ordered by balance descending as a proxy — highest
balance receives the marginal payment first.

Balance convention: credit and loan accounts store their balance as a negative
float (e.g. -2340.15).  This module converts those to positive debt amounts
internally for all amortisation maths.
"""

import datetime

from ..models.account import Account, AccountType

# Default annual percentage rate used when no per-account rate is available.
DEFAULT_APR_PCT: float = 20.0

# Maximum simulation horizon in months (30 years).
_MAX_MONTHS: int = 360


def _payoff_month_label(start: datetime.date, months_offset: int) -> str:
    """Return a YYYY-MM string for *start* advanced by *months_offset* months."""
    year = start.year + (start.month - 1 + months_offset) // 12
    month = (start.month - 1 + months_offset) % 12 + 1
    return f"{year:04d}-{month:02d}"


def _simulate_debt(
    balance: float,
    monthly_rate: float,
    monthly_payment: float,
    lump_sum: float,
    start: datetime.date,
) -> tuple[int, float, str]:
    """Simulate a single debt to payoff.

    Parameters
    ----------
    balance:
        Positive outstanding principal.
    monthly_rate:
        APR / 12 expressed as a decimal (e.g. 0.2/12).
    monthly_payment:
        Regular monthly payment applied to this debt.
    lump_sum:
        One-time extra payment applied in month 1.
    start:
        Simulation start date (today).

    Returns
    -------
    (payoff_months, total_interest_paid, payoff_date_label)
    """
    remaining = balance - lump_sum
    if remaining <= 0:
        return 0, 0.0, _payoff_month_label(start, 0)

    total_interest = 0.0
    for month in range(1, _MAX_MONTHS + 1):
        interest = remaining * monthly_rate
        total_interest += interest
        remaining = remaining + interest - monthly_payment
        if remaining <= 0:
            return month, round(total_interest, 2), _payoff_month_label(start, month)

    # Debt not paid off within the horizon — return sentinel values.
    return _MAX_MONTHS, round(total_interest, 2), _payoff_month_label(start, _MAX_MONTHS)


def calculate_debt_payoff(
    accounts: list[Account],
    monthly_payment: float,
    extra_payment: float = 0.0,
) -> dict:
    """Project debt payoff dates and total interest using the avalanche method.

    The avalanche method prioritises debts with the highest balance (used here
    as a proxy for rate since no rate data is available in the schema).  The
    minimum required to service each debt is the interest accrued in that month
    plus one dollar; any remaining payment from *monthly_payment* is directed
    at the highest-balance debt.

    Parameters
    ----------
    accounts:
        Full list of accounts loaded by a loader.  Non-debt accounts are
        ignored automatically.
    monthly_payment:
        Total monthly payment to distribute across all outstanding debts.
    extra_payment:
        Optional one-time lump sum applied in month 1 to the highest-balance
        debt before the regular payment is distributed.

    Returns
    -------
    dict with keys:
        debts                  — per-account amortisation results
        total_balance          — sum of all outstanding balances
        total_monthly_payment  — *monthly_payment* as supplied
        projected_debt_free_date — latest payoff_date across all debts (YYYY-MM)
        total_interest_paid    — sum of interest paid across all debts
    """
    # --- Filter to debt accounts ---
    debt_subtypes = {"credit_card", "line_of_credit", "loan"}
    debt_accounts = [
        a
        for a in accounts
        if a.type == AccountType.CREDIT or a.type == AccountType.LOAN or a.subtype in debt_subtypes
    ]

    if not debt_accounts:
        today = datetime.date.today()
        return {
            "debts": [],
            "total_balance": 0.0,
            "total_monthly_payment": round(monthly_payment, 2),
            "projected_debt_free_date": today.strftime("%Y-%m"),
            "total_interest_paid": 0.0,
        }

    today = datetime.date.today()
    monthly_rate = (DEFAULT_APR_PCT / 100.0) / 12.0

    # Build working list: (account, positive_balance)
    # Balances are stored as negative; abs() converts to owed amount.
    debt_list = [(a, abs(a.balance)) for a in debt_accounts if abs(a.balance) > 0]

    if not debt_list:
        return {
            "debts": [],
            "total_balance": 0.0,
            "total_monthly_payment": round(monthly_payment, 2),
            "projected_debt_free_date": today.strftime("%Y-%m"),
            "total_interest_paid": 0.0,
        }

    # Avalanche proxy: sort by balance descending (highest balance first).
    debt_list.sort(key=lambda x: x[1], reverse=True)

    # --- Distribute monthly_payment across debts ---
    # Strategy:
    #   1. Each debt receives at minimum its monthly interest + $1 (keeps it
    #      from growing); the first debt in the sorted order receives any
    #      remaining payment above those minimums.
    #   2. extra_payment is applied as a lump sum to the highest-balance debt
    #      in month 1 only.
    #   3. Each debt is then simulated independently with its assigned payment.
    #
    # Compute minimum payment per debt (interest + $1 floor).
    minimums = [balance * monthly_rate + 1.0 for _, balance in debt_list]

    results = []
    remaining_payment = monthly_payment

    for idx, (account, balance) in enumerate(debt_list):
        if idx == 0:
            # Highest-balance debt gets all surplus after minimums for others.
            other_minimums = sum(minimums[1:])
            payment_for_this = max(remaining_payment - other_minimums, minimums[0])
            lump = extra_payment  # extra payment goes here only
        else:
            payment_for_this = minimums[idx]
            lump = 0.0

        payoff_months, total_interest, payoff_date = _simulate_debt(
            balance=balance,
            monthly_rate=monthly_rate,
            monthly_payment=payment_for_this,
            lump_sum=lump,
            start=today,
        )

        results.append(
            {
                "account_id": account.account_id,
                "name": account.name,
                "balance": round(balance, 2),
                "assumed_apr_pct": DEFAULT_APR_PCT,
                "payoff_months": payoff_months,
                "payoff_date": payoff_date,
                "total_interest_paid": total_interest,
            }
        )

    total_balance = round(sum(b for _, b in debt_list), 2)
    total_interest_paid = round(sum(r["total_interest_paid"] for r in results), 2)

    # Debt-free date is the latest individual payoff date.
    projected_debt_free_date = max(r["payoff_date"] for r in results)

    return {
        "debts": results,
        "total_balance": total_balance,
        "total_monthly_payment": round(monthly_payment, 2),
        "projected_debt_free_date": projected_debt_free_date,
        "total_interest_paid": total_interest_paid,
    }
