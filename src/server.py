import os
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.calculators.budget import calculate_budget_breakdown
from src.calculators.budget import list_budget_models as _list_budget_models
from src.calculators.budget_models import DEFAULT_MODEL
from src.calculators.debt_payoff import calculate_debt_payoff
from src.calculators.net_worth import calculate_net_worth
from src.calculators.performance import calculate_brokerage_performance
from src.calculators.savings_rate import calculate_savings_rate
from src.calculators.spending_trends import calculate_spending_trends
from src.loaders.base import BaseLoader
from src.loaders.capital_one_loader import CapitalOneLoader
from src.loaders.composite_loader import CompositeLoader
from src.loaders.csv_loader import CSVLoader
from src.loaders.fidelity_loader import FidelityLoader
from src.loaders.qfx_loader import QFXLoader
from src.loaders.vanguard_loader import VanguardLoader
from src.usage_logger import log_tool_call
from src.validators import (
    validate_account_id,
    validate_data_dir,
    validate_date,
    validate_model,
)

_root = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv

    _env = os.getenv("MIDAS_ENV")
    load_dotenv(_root / (f".env.{_env}" if _env else ".env"))
except ImportError:
    pass

_DEFAULT_DATA = _root / "data" / "sample"
DATA_DIR = Path(os.getenv("MIDAS_DATA_DIR", _DEFAULT_DATA))
if not DATA_DIR.is_absolute():
    DATA_DIR = _root / DATA_DIR

_data_root_env = os.getenv("MIDAS_DATA_ROOT")
DATA_ROOT = Path(_data_root_env) if _data_root_env else None
if DATA_ROOT and not DATA_ROOT.is_absolute():
    DATA_ROOT = _root / DATA_ROOT

if DATA_ROOT is None:
    validate_data_dir(DATA_DIR)

mcp = FastMCP(
    "midas",
    instructions=(
        "Personal finance assistant. Tools: get_net_worth, get_budget_breakdown, "
        "get_brokerage_performance, get_savings_rate, get_spending_trends. Dates are YYYY-MM-DD."
    ),
)


def _loader() -> BaseLoader:
    if DATA_ROOT is not None:
        loaders = []
        if (DATA_ROOT / "capital one").exists():
            loaders.append(CapitalOneLoader(DATA_ROOT / "capital one"))
        if (DATA_ROOT / "adp").exists():
            loaders.append(QFXLoader(DATA_ROOT / "adp"))
        if (DATA_ROOT / "fidelity").exists():
            loaders.append(FidelityLoader(DATA_ROOT / "fidelity"))
        if (DATA_ROOT / "vanguard").exists():
            loaders.append(VanguardLoader(DATA_ROOT / "vanguard"))
        return CompositeLoader(loaders)
    return CSVLoader(DATA_DIR)


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_net_worth() -> dict:
    """Return current net worth: total assets minus total liabilities, broken down by account."""
    loader = _loader()
    return calculate_net_worth(loader.load_accounts(), loader.load_holdings())


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_budget_breakdown(
    start_date: str | None = None,
    end_date: str | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Return a budget breakdown for a date range (YYYY-MM-DD).

    model options (use list_budget_models to see all):
      50_30_20   — Needs / Wants / Savings (default)
      70_20_10   — Living / Savings / Giving & Debt
      80_20      — Pay yourself first: Save 20%, spend 80%
      zero_based — Every dollar assigned; shows per-category line items

    Omit dates to include all transactions.
    """
    if start_date is not None:
        validate_date(start_date)
    if end_date is not None:
        validate_date(end_date)
    validate_model(model)
    loader = _loader()
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    return calculate_budget_breakdown(loader.load_transactions(), sd, ed, model)


@mcp.tool()
@log_tool_call(DATA_DIR)
def list_budget_models() -> list[dict]:
    """List all available budget models with their keys, names, and descriptions."""
    return _list_budget_models()


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_brokerage_performance(account_id: str | None = None) -> dict:
    """
    Return brokerage holdings: value, cost basis, gain/loss, allocation per position.
    Pass account_id to filter to a single account; omit for all investment accounts.
    """
    if account_id is not None:
        validate_account_id(account_id)
    loader = _loader()
    return calculate_brokerage_performance(loader.load_holdings(), account_id)


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_savings_rate(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Return savings rate for a date range: income vs. intentional savings (savings + retirement categories)."""
    if start_date is not None:
        validate_date(start_date)
    if end_date is not None:
        validate_date(end_date)
    loader = _loader()
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    return calculate_savings_rate(loader.load_transactions(), sd, ed)


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_spending_trends(months: int = 6) -> dict:
    """Return month-over-month spending trends for the last N months."""
    loader = _loader()
    return calculate_spending_trends(loader.load_transactions(), months)


@mcp.tool()
@log_tool_call(DATA_DIR)
def get_debt_payoff_projection(
    monthly_payment: float,
    extra_payment: float = 0.0,
) -> dict:
    """
    Project when all debts will be paid off and the total interest cost.

    Uses the avalanche method (highest balance first as a proxy for rate,
    since APR data is not stored in the schema). Assumes 20% APR for all debts.

    monthly_payment — total monthly payment to distribute across all debts.
    extra_payment   — optional one-time lump sum applied in month 1 to the
                      highest-balance debt (default 0).
    """
    loader = _loader()
    return calculate_debt_payoff(loader.load_accounts(), monthly_payment, extra_payment)


def main() -> None:
    from src.usage_logger import _is_sample

    if not _is_sample(DATA_DIR):
        import sys

        print(
            f"[midas] WARNING: running with real data at {DATA_DIR} — logs are redacted",
            file=sys.stderr,
        )
    mcp.run()


if __name__ == "__main__":
    main()
