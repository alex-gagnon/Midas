"""Composite loader that aggregates multiple BaseLoader instances into one."""

from ..models.account import Account
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader


class CompositeLoader(BaseLoader):
    """Aggregates multiple BaseLoader instances into one.

    Each method delegates to every contained loader and concatenates the
    results in the order the loaders were provided.

    Args:
        loaders: List of ``BaseLoader`` instances to aggregate.
    """

    def __init__(self, loaders: list[BaseLoader]) -> None:
        self.loaders = loaders

    def load_accounts(self) -> list[Account]:
        return [a for loader in self.loaders for a in loader.load_accounts()]

    def load_transactions(self) -> list[Transaction]:
        return [t for loader in self.loaders for t in loader.load_transactions()]

    def load_holdings(self) -> list[Holding]:
        return [h for loader in self.loaders for h in loader.load_holdings()]
