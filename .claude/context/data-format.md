# Data Format

CSV files live in a directory (default: `data/sample/`), set via `MIDAS_DATA_DIR`.

## accounts.csv
Columns: `account_id, name, institution, type, subtype, balance, currency`

`type` values: `depository`, `credit`, `investment`, `loan`

## transactions.csv
Columns: `date, amount, description, category, account_id`

`date` format: `YYYY-MM-DD`

## holdings.csv
Columns: `account_id, symbol, name, shares, cost_basis_per_share, current_price`
