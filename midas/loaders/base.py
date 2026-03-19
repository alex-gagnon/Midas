from abc import ABC, abstractmethod

from ..models.account import Account
from ..models.holding import Holding
from ..models.transaction import Transaction


class BaseLoader(ABC):
    @abstractmethod
    def load_accounts(self) -> list[Account]: ...

    @abstractmethod
    def load_transactions(self) -> list[Transaction]: ...

    @abstractmethod
    def load_holdings(self) -> list[Holding]: ...
