import os
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.calculators.budget import calculate_budget_breakdown
from src.calculators.budget import list_budget_models as _list_budget_models
from src.calculators.budget_models import DEFAULT_MODEL
from src.calculators.net_worth import calculate_net_worth
from src.calculators.performance import calculate_brokerage_performance
from src.loaders.csv_loader import CSVLoader

_DEFAULT_DATA = Path(__file__).parent.parent / "data" / "sample"
DATA_DIR = Path(os.getenv("MIDAS_DATA_DIR", _DEFAULT_DATA))

mcp = FastMCP(
    "midas",
    instructions=(
        "Personal finance assistant. Tools: get_net_worth, get_budget_breakdown, "
        "get_brokerage_performance. Dates are YYYY-MM-DD."
    ),
)


def _loader() -> CSVLoader:
    return CSVLoader(DATA_DIR)


@mcp.tool()
def get_net_worth() -> dict:
    """Return current net worth: total assets minus total liabilities, broken down by account."""
    loader = _loader()
    return calculate_net_worth(loader.load_accounts(), loader.load_holdings())


@mcp.tool()
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
    loader = _loader()
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    return calculate_budget_breakdown(loader.load_transactions(), sd, ed, model)


@mcp.tool()
def list_budget_models() -> list[dict]:
    """List all available budget models with their keys, names, and descriptions."""
    return _list_budget_models()


@mcp.tool()
def get_brokerage_performance(account_id: str | None = None) -> dict:
    """
    Return brokerage holdings: value, cost basis, gain/loss, allocation per position.
    Pass account_id to filter to a single account; omit for all investment accounts.
    """
    loader = _loader()
    return calculate_brokerage_performance(loader.load_holdings(), account_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
