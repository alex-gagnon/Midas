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
- [ ] **CSV data validation** — check required columns, value types, and referential integrity at load time; surface a clear error instead of a cryptic `KeyError`
- [ ] **Historical performance tracking** — `portfolio_snapshots.csv` schema + `get_net_worth_history()` tool for year-over-year net worth and portfolio trends

## Backlog
- [ ] Implement Plaid loader as a live data source alternative to CSV
