"""
Plaid API loader — future live-data integration.

Required env vars when implemented:
  PLAID_CLIENT_ID
  PLAID_SECRET
  PLAID_ENV            sandbox | development | production
  PLAID_ACCESS_TOKENS  comma-separated access tokens per linked institution

Install extra dep when wiring up:  plaid-python>=20.0.0
"""

from ..models.account import Account
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader


class PlaidLoader(BaseLoader):
    def __init__(self, client_id: str, secret: str, env: str = "sandbox"):
        self.client_id = client_id
        self.secret = secret
        self.env = env
        # TODO: initialize plaid.ApiClient + AccountsApi / TransactionsApi / InvestmentsApi

    def load_accounts(self) -> list[Account]:
        raise NotImplementedError

    def load_transactions(self) -> list[Transaction]:
        raise NotImplementedError

    def load_holdings(self) -> list[Holding]:
        raise NotImplementedError
