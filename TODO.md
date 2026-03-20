# TODO

## Data / loader fixes (from financial analyst audit, 2026-03-20)

### 🔴 Critical
- [ ] **Add checking account loader** — primary checking account missing from net worth; total cash assets are understated
- [ ] **Add mortgage/real estate support** — homeownership is implied by data patterns; both home asset and mortgage liability are absent, making net worth unreliable
- [ ] **Fix credit card balance source** — `CapitalOneLoader` computes credit card balance from transaction history rather than an authoritative balance field; the computed figure is net spend minus payments for the export window, not the true current balance

### 🟡 Warning
- [ ] **Include money market in investment account net worth** — money market positions are excluded from `holdings_value` because they are filtered out before holdings are built; net worth systematically undercounts liquid reserves in investment accounts
- [ ] **Classify IRA accounts correctly** — at least one investment account is an IRA but the loader hardcodes `subtype="brokerage"` for all accounts, breaking tax-efficiency analysis
- [ ] **Brokerage cost basis missing** — one loader sets `cost_basis_per_share=0.0` for all holdings because the export format omits it; `get_brokerage_performance` will report 0% return and $0 gain/loss for all affected positions

## Up next
- [ ] **Debt payoff projections** — add calculator tool, natural continuation of savings rate / spending trends work
- [ ] **New budget models** — add new budget model types to the budget calculator

## Backlog
- [ ] Historical performance data
- [ ] Implement Plaid loader as a live data source alternative to CSV *(requires secrets management above)*

## Done
- [x] **Log hygiene** — redact sensitive args in `logs/usage.jsonl` when not using sample data
- [x] **Input validation** — validate tool params and `MIDAS_DATA_DIR` at server startup
- [x] **Secrets management** — add `.env.example`, document env var conventions, update `.gitignore`
- [x] **Access control** — document transport security model; add startup warning for real data
- [x] **Add savings rate and spending trends calculator tools** — `get_savings_rate` and `get_spending_trends` implemented and tested
- [x] **Linting** — ruff configured in `pyproject.toml`, violations fixed, `.ruff_cache/` gitignored
- [x] **.claude tooling** — context, commands (`/lint`, `/test`), and agent definitions updated to reflect current project state
