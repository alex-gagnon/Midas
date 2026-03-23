import logging
from pathlib import Path

from ofxparse import OfxParser

from ..models.account import Account, AccountType
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader

logger = logging.getLogger(__name__)

# Map OFX account types to Midas AccountType enum
_ACCOUNT_TYPE_MAP = {
    "CHECKING": AccountType.DEPOSITORY,
    "SAVINGS": AccountType.DEPOSITORY,
    "CREDITLINE": AccountType.CREDIT,
    "MONEYMRKT": AccountType.CREDIT,
    "INVESTMENT": AccountType.INVESTMENT,
    "401K": AccountType.INVESTMENT,
    "IRA": AccountType.INVESTMENT,
}

# OFX transaction types that map to the "income" category
_INCOME_TYPES = {"CREDIT", "DEP", "INT", "DIV", "REINVEST"}

# OFX investment transaction types that map to the "investment" category
_INVESTMENT_TYPES = {"BUYMF", "SELLMF", "BUYSTOCK", "SELLSTOCK"}


class QFXLoader(BaseLoader):
    """Loads financial data from QFX/OFX files.

    Scans ``data_dir`` for all ``*.qfx`` and ``*.ofx`` files and parses each
    one using the ``ofxparse`` library.  Malformed files are skipped with a
    warning rather than raising an exception so that a single bad file does not
    block the entire load.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_ofx_files(self) -> list[Path]:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        return list(self.data_dir.glob("*.qfx")) + list(self.data_dir.glob("*.ofx"))

    def _parse_file(self, path: Path):
        try:
            with open(path, "rb") as f:
                return OfxParser.parse(f)
        except Exception as exc:
            logger.warning("Skipping malformed QFX/OFX file %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------
    # BaseLoader interface
    # ------------------------------------------------------------------

    def load_accounts(self) -> list[Account]:
        accounts = []
        for path in self._iter_ofx_files():
            ofx = self._parse_file(path)
            if ofx is None or ofx.account is None:
                continue
            acct = ofx.account
            raw_type = getattr(acct, "account_type", "") or ""

            # Investment accounts (e.g. ADP 401k) have an empty account_type
            # but expose positions on their statement.  Detect and promote them.
            stmt = acct.statement
            has_positions = bool(stmt and getattr(stmt, "positions", None))
            if raw_type == "" and has_positions:
                acct_type = AccountType.INVESTMENT
            else:
                acct_type = _ACCOUNT_TYPE_MAP.get(raw_type.upper(), AccountType.DEPOSITORY)

            institution = ""
            if hasattr(acct, "institution") and acct.institution:
                institution = getattr(acct.institution, "organization", "") or ""

            balance = 0.0
            if stmt is not None:
                # Bank statements expose .balance; investment statements do not.
                # Fall back to summing position market values for investment accounts.
                raw_balance = getattr(stmt, "balance", None)
                if raw_balance is not None:
                    balance = float(raw_balance)
                elif has_positions:
                    balance = sum(float(p.market_value) for p in stmt.positions)

            accounts.append(
                Account(
                    account_id=acct.account_id,
                    name=path.stem,
                    institution=institution,
                    type=acct_type,
                    subtype=raw_type.lower(),
                    balance=balance,
                    currency="USD",
                )
            )
        return accounts

    def load_transactions(self) -> list[Transaction]:
        transactions = []
        for path in self._iter_ofx_files():
            ofx = self._parse_file(path)
            if ofx is None or ofx.account is None:
                continue
            acct = ofx.account
            if not acct.statement:
                continue

            # Skip investment accounts (e.g. 401k) — their transactions are
            # portfolio buys/reinvestments, not personal cash flow.
            stmt = acct.statement
            has_positions = bool(getattr(stmt, "positions", None))
            raw_type = getattr(acct, "account_type", "") or ""
            if raw_type == "" and has_positions:
                continue

            account_id = acct.account_id
            for txn in acct.statement.transactions:
                trntype = getattr(txn, "type", "") or ""
                trntype_upper = trntype.upper()
                if trntype_upper in _INCOME_TYPES:
                    category = "income"
                elif trntype_upper in _INVESTMENT_TYPES:
                    category = "investment"
                else:
                    category = "uncategorized"

                description = getattr(txn, "memo", "") or getattr(txn, "payee", "") or ""

                # Bank transactions use .date; investment transactions use .tradeDate.
                txn_date = getattr(txn, "date", None) or getattr(txn, "tradeDate", None)
                if txn_date is None:
                    logger.warning(
                        "Transaction %s in %s has no date; skipping", getattr(txn, "id", "?"), path
                    )
                    continue
                if hasattr(txn_date, "date"):
                    txn_date = txn_date.date()

                # Bank transactions use .amount; investment transactions use .total.
                amount = getattr(txn, "amount", None)
                if amount is None:
                    amount = getattr(txn, "total", None)
                if amount is None:
                    amount = 0.0

                transactions.append(
                    Transaction(
                        date=txn_date,
                        amount=float(amount),
                        description=description,
                        account_id=account_id,
                        category=category,
                    )
                )
        return transactions

    def load_holdings(self) -> list[Holding]:
        holdings = []
        for path in self._iter_ofx_files():
            ofx = self._parse_file(path)
            if ofx is None or ofx.account is None:
                continue
            acct = ofx.account
            stmt = acct.statement
            if stmt is None:
                continue
            positions = getattr(stmt, "positions", [])
            if not positions:
                continue

            # Build CUSIP → Security map from the file-level security list.
            sec_map: dict[str, object] = {}
            for sec in getattr(ofx, "security_list", []) or []:
                uid = getattr(sec, "uniqueid", None)
                if uid:
                    sec_map[uid] = sec

            account_id = acct.account_id
            for pos in positions:
                cusip = pos.security  # ofxparse returns the CUSIP as a plain string
                sec = sec_map.get(cusip)
                symbol = (getattr(sec, "ticker", None) or cusip) if sec else cusip
                name = (getattr(sec, "name", None) or "") if sec else ""

                holdings.append(
                    Holding(
                        account_id=account_id,
                        symbol=symbol,
                        name=name,
                        shares=float(pos.units),
                        cost_basis_per_share=0.0,  # QFX does not include cost basis
                        current_price=float(pos.unit_price),
                    )
                )
        return holdings
