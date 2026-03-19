from dataclasses import dataclass
from enum import Enum


class AccountType(str, Enum):
    DEPOSITORY = "depository"
    CREDIT = "credit"
    INVESTMENT = "investment"
    LOAN = "loan"


@dataclass
class Account:
    account_id: str
    name: str
    institution: str
    type: AccountType
    subtype: str
    balance: float  # positive = asset value, negative = amount owed
    currency: str = "USD"

    @property
    def is_asset(self) -> bool:
        return self.type in (AccountType.DEPOSITORY, AccountType.INVESTMENT)

    @property
    def is_liability(self) -> bool:
        return self.type in (AccountType.CREDIT, AccountType.LOAN)
