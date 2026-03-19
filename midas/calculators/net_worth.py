from ..models.account import Account, AccountType
from ..models.holding import Holding


def calculate_net_worth(accounts: list[Account], holdings: list[Holding]) -> dict:
    # Sum current market value per investment account
    holdings_value: dict[str, float] = {}
    for h in holdings:
        holdings_value[h.account_id] = holdings_value.get(h.account_id, 0.0) + h.current_value

    assets: dict[str, float] = {}
    liabilities: dict[str, float] = {}

    for account in accounts:
        if account.type == AccountType.INVESTMENT:
            value = holdings_value.get(account.account_id, 0.0)
        else:
            value = account.balance

        if account.is_asset:
            assets[account.name] = round(value, 2)
        elif account.is_liability:
            # Balances are stored negative; expose as positive debt amount
            liabilities[account.name] = round(abs(value), 2)

    total_assets = sum(assets.values())
    total_liabilities = sum(liabilities.values())

    return {
        "net_worth": round(total_assets - total_liabilities, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "assets": assets,
        "liabilities": liabilities,
    }
