# Midas

A personal finance [MCP](https://modelcontextprotocol.io/) server that gives AI assistants real insight into your money. Ask Claude about your net worth, analyze your spending against popular budget frameworks, or review your brokerage performance — all from a simple chat.

Built with [FastMCP](https://github.com/jlowin/fastmcp) and backed by plain CSV files.

---

## What it does

Midas exposes four tools over the Model Context Protocol:

| Tool | What it answers |
|---|---|
| `get_net_worth` | Total assets minus liabilities, broken down by account |
| `get_budget_breakdown` | How your spending stacks up against a budget model for any date range |
| `list_budget_models` | All available budget frameworks with descriptions |
| `get_brokerage_performance` | Holdings value, cost basis, gain/loss, and allocation per position |

### Budget models

Pick the framework that fits how you think about money:

- **50/30/20** — Needs / Wants / Savings (default)
- **70/20/10** — Living expenses / Savings / Giving & debt
- **80/20** — Pay yourself first: save 20%, spend the rest freely
- **Zero-based** — Every dollar gets a job; per-category line items

---

## Getting started

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
# Install dependencies
uv pip install -e .

# Run the server
midas
```

Or without installing:

```bash
python main.py
```

The server starts and listens for MCP connections. Point your MCP client (e.g. Claude Desktop) at it.

---

## Your data

Data lives in CSV files under a directory you control. The server defaults to `data/sample/` — point it at your own files with an environment variable:

```bash
MIDAS_DATA_DIR=/path/to/your/data midas
```

### File schemas

**`accounts.csv`**
```
account_id, name, institution, type, subtype, balance, currency
```
Account types: `depository`, `credit`, `investment`, `loan`

**`transactions.csv`**
```
date, amount, description, category, account_id
```
Date format: `YYYY-MM-DD`

**`holdings.csv`**
```
account_id, symbol, name, shares, cost_basis_per_share, current_price
```

---

## Project layout

```
src/
  server.py          # MCP tool definitions and entry point
  models/            # Dataclasses: Account, Holding, Transaction
  loaders/
    csv_loader.py    # Reads your CSV files
    plaid_loader.py  # Alternative: load from Plaid API
  calculators/
    net_worth.py     # Assets minus liabilities
    budget.py        # Budget breakdown logic
    budget_models.py # Model definitions (50/30/20, zero-based, etc.)
    performance.py   # Brokerage gain/loss and allocation
main.py              # Entry point
data/sample/         # Sample CSV files to get started
```

