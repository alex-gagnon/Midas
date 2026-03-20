from ..models.holding import Holding


def calculate_brokerage_performance(
    holdings: list[Holding],
    account_id: str | None = None,
) -> dict:
    if account_id:
        holdings = [h for h in holdings if h.account_id == account_id]

    total_value = sum(h.current_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_gain_loss = total_value - total_cost
    total_return_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0.0

    positions = []
    for h in holdings:
        positions.append(
            {
                "symbol": h.symbol,
                "name": h.name,
                "account_id": h.account_id,
                "shares": h.shares,
                "current_price": round(h.current_price, 2),
                "current_value": round(h.current_value, 2),
                "cost_basis": round(h.cost_basis, 2),
                "gain_loss": round(h.gain_loss, 2),
                "gain_loss_pct": round(h.gain_loss_pct, 2),
                "allocation_pct": round(h.current_value / total_value * 100, 1)
                if total_value > 0
                else 0.0,
            }
        )

    positions.sort(key=lambda p: p["current_value"], reverse=True)

    return {
        "filter": {"account_id": account_id},
        "summary": {
            "total_value": round(total_value, 2),
            "total_cost_basis": round(total_cost, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_return_pct": round(total_return_pct, 2),
            "position_count": len(positions),
        },
        "positions": positions,
    }
