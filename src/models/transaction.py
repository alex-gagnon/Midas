from dataclasses import dataclass
from datetime import date


@dataclass
class Transaction:
    date: date
    amount: float  # positive = income/credit, negative = expense/debit
    description: str
    category: str
    account_id: str
