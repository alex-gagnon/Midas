# Midas

> **Status: Early development (v0.1.0)** — core tools are working, CSV data source is fully supported, live Plaid integration is not yet implemented.

A personal finance [MCP](https://modelcontextprotocol.io/) server that gives AI assistants real insight into your money. Ask Claude about your net worth, analyze your spending against popular budget frameworks, or review your brokerage performance — all from a simple chat.

Built with [FastMCP](https://github.com/jlowin/fastmcp) and backed by plain CSV files.

---

## MCP tools

Midas exposes four tools over the Model Context Protocol:

---

### `get_net_worth`
Returns total assets minus total liabilities, broken down by account.

No parameters.

---

### `get_budget_breakdown`
Scores your spending against a budget model for a given date range.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_date` | `string` | all time | Start of date range (`YYYY-MM-DD`) |
| `end_date` | `string` | all time | End of date range (`YYYY-MM-DD`) |
| `model` | `string` | `50_30_20` | Budget model to apply (see below) |

**Budget models:**

| Key | Name | Description |
|---|---|---|
| `50_30_20` | 50/30/20 | 50% needs, 30% wants, 20% savings & debt (default) |
| `70_20_10` | 70/20/10 | 70% living expenses, 20% savings, 10% giving & debt |
| `80_20` | 80/20 | Save 20% off the top; spend the remaining 80% freely |
| `zero_based` | Zero-based | Every dollar assigned; per-category line items |

---

### `list_budget_models`
Returns all available budget models with their keys, names, and descriptions.

No parameters.

---

### `get_brokerage_performance`
Returns holdings value, cost basis, gain/loss, return percentage, and allocation for each position.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `account_id` | `string` | all accounts | Filter to a single investment account |

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
python -m src.server
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

## Security

- **Claude Desktop** uses the stdio transport — all communication stays on your local machine; there is no network exposure.
- **`mcp dev`** uses an HTTP proxy with an access token. Only run it locally (loopback interface). Never bind `mcp dev` to a non-loopback interface when using real financial data.
- When `MIDAS_DATA_DIR` points to real (non-sample) data, tool argument logs in `logs/usage.jsonl` are automatically redacted — only date and model params are written in plain text. A startup warning is printed to stderr.

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

