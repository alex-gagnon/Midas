# TODO

## Up next

## Backlog
- [ ] Implement Plaid loader as a live data source alternative to CSV *(requires secrets management above)*

## Done
- [x] **Log hygiene** — redact sensitive args in `logs/usage.jsonl` when not using sample data
- [x] **Input validation** — validate tool params and `MIDAS_DATA_DIR` at server startup
- [x] **Secrets management** — add `.env.example`, document env var conventions, update `.gitignore`
- [x] **Access control** — document transport security model; add startup warning for real data
- [x] **Add savings rate and spending trends calculator tools** — `get_savings_rate` and `get_spending_trends` implemented and tested
- [x] **Linting** — ruff configured in `pyproject.toml`, violations fixed, `.ruff_cache/` gitignored
- [x] **.claude tooling** — context, commands (`/lint`, `/test`), and agent definitions updated to reflect current project state
- [x] **Debt payoff projections** — `get_debt_payoff_projection` tool implemented with avalanche method, tested
- [x] **New budget models** — added `60_20_20` (aggressive savings) and `kakeibo` (Japanese envelope method) models
