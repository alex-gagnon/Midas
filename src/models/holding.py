from dataclasses import dataclass


@dataclass
class Holding:
    account_id: str
    symbol: str
    name: str
    shares: float
    cost_basis_per_share: float
    current_price: float

    @property
    def current_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.cost_basis_per_share

    @property
    def gain_loss(self) -> float:
        return self.current_value - self.cost_basis

    @property
    def gain_loss_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.gain_loss / self.cost_basis) * 100
