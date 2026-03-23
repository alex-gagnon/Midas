# TODO

## Up next
- [ ] **CSV data validation** — validate schema at load time: check required columns are present in each file, verify value types/formats (dates, floats, account type enum), and enforce referential integrity (every `account_id` in `transactions.csv` and `holdings.csv` must exist in `accounts.csv`); raise `ValueError` with a clear, actionable message instead of a cryptic `KeyError` or `AttributeError`
- [ ] **Historical performance tracking** — add a `portfolio_snapshots.csv` schema (date, account_id, value) for periodic snapshots and a `get_net_worth_history(period)` MCP tool that returns a time-series of net worth, assets, and liabilities to enable year-over-year tracking

## Backlog
- [ ] Implement Plaid loader as a live data source alternative to CSV *(requires secrets management above)*

## Done
- [x] **Net worth** — `get_net_worth` implemented: assets minus liabilities, investment accounts use holdings value rather than account balance
- [x] **Budget breakdown** — `get_budget_breakdown` and `list_budget_models` implemented with 6 models (50/30/20, 70/20/10, 80/20, 60/20/20, zero-based, kakeibo)
- [x] **Brokerage performance snapshot** — `get_brokerage_performance` implemented: holdings value, cost basis, gain/loss, and allocation % per position
- [x] **Log hygiene** — redact sensitive args in `logs/usage.jsonl` when not using sample data
- [x] **Input validation** — validate tool params and `MIDAS_DATA_DIR` at server startup
- [x] **Secrets management** — add `.env.example`, document env var conventions, update `.gitignore`
- [x] **Access control** — document transport security model; add startup warning for real data
- [x] **Add savings rate and spending trends calculator tools** — `get_savings_rate` and `get_spending_trends` implemented and tested
- [x] **Linting** — ruff configured in `pyproject.toml`, violations fixed, `.ruff_cache/` gitignored
- [x] **.claude tooling** — context, commands (`/lint`, `/test`), and agent definitions updated to reflect current project state
- [x] **Debt payoff projections** — `get_debt_payoff_projection` tool implemented with avalanche method, tested
- [x] **New budget models** — added `60_20_20` (aggressive savings) and `kakeibo` (Japanese envelope method) models
- [x] **Budget/savings default date range** — `get_budget_breakdown` and `get_savings_rate` now default to the current calendar month instead of all-time, preventing cross-period expense aggregation
