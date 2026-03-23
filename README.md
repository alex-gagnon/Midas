# Midas

A personal finance [MCP](https://modelcontextprotocol.io/) server that gives AI assistants real insight into your money. Ask Claude about your net worth, analyze your spending against popular budget frameworks, or review your brokerage performance — all from a simple chat.

Built with [FastMCP](https://github.com/jlowin/fastmcp) and backed by plain CSV files.

---

## MCP tools

### `get_net_worth`
Returns total assets minus total liabilities, broken down by account.

No parameters.

---

### `get_budget_breakdown`
Scores your spending against a budget model for a given date range. Defaults to the current calendar month.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_date` | `string` | start of current month | Start of date range (`YYYY-MM-DD`) |
| `end_date` | `string` | today | End of date range (`YYYY-MM-DD`) |
| `model` | `string` | `50_30_20` | Budget model to apply (see below) |

**Budget models:**

| Key | Name | Description |
|---|---|---|
| `50_30_20` | 50/30/20 | 50% needs, 30% wants, 20% savings & debt (default) |
| `70_20_10` | 70/20/10 | 70% living expenses, 20% savings, 10% giving & debt |
| `80_20` | 80/20 | Save 20% off the top; spend the remaining 80% freely |
| `60_20_20` | 60/20/20 | 60% living, 20% savings, 20% wants |
| `zero_based` | Zero-based | Every dollar assigned; per-category line items |
| `kakeibo` | Kakeibo | Japanese method: needs, wants, culture, unexpected |

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

### `get_savings_rate`
Returns income vs. intentional savings (savings + retirement categories) for a date range. Defaults to the current calendar month.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_date` | `string` | start of current month | Start of date range (`YYYY-MM-DD`) |
| `end_date` | `string` | today | End of date range (`YYYY-MM-DD`) |

---

### `get_spending_trends`
Returns month-over-month spending trends for the last N months.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `months` | `integer` | `6` | Number of months to look back |

---

### `get_debt_payoff_projection`
Projects when all debts will be paid off and the total interest cost using the avalanche method.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `monthly_payment` | `float` | required | Total monthly payment to distribute across all debts |
| `extra_payment` | `float` | `0.0` | One-time lump sum applied in month 1 |

---

## Getting started

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
uv pip install -e .
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
