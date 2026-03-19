"""Unit tests for src/calculators/net_worth.py."""

import pytest

from src.calculators.net_worth import calculate_net_worth
from src.models.account import Account, AccountType
from src.models.holding import Holding


def _account(account_id, name, acct_type, balance):
    return Account(account_id, name, "Bank", acct_type, "sub", balance)


def _holding(account_id, symbol, shares, cost, price):
    return Holding(account_id, symbol, symbol, shares, cost, price)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestNetWorthReturnShape:
    def test_keys_present(self):
        result = calculate_net_worth([], [])
        assert set(result.keys()) == {"net_worth", "total_assets", "total_liabilities", "assets", "liabilities"}

    def test_empty_inputs_all_zero(self):
        result = calculate_net_worth([], [])
        assert result["net_worth"] == 0.0
        assert result["total_assets"] == 0.0
        assert result["total_liabilities"] == 0.0
        assert result["assets"] == {}
        assert result["liabilities"] == {}


# ---------------------------------------------------------------------------
# Asset classification
# ---------------------------------------------------------------------------


class TestAssetClassification:
    def test_depository_balance_in_assets(self):
        accounts = [_account("chk_001", "Checking", AccountType.DEPOSITORY, 5_000.0)]
        result = calculate_net_worth(accounts, [])
        assert result["assets"]["Checking"] == 5_000.0
        assert "Checking" not in result["liabilities"]

    def test_investment_account_uses_holdings_value_not_balance(self):
        # Balance is 0 but holdings are worth 2500
        accounts = [_account("inv_001", "Brokerage", AccountType.INVESTMENT, 0.0)]
        holdings = [_holding("inv_001", "VTI", 10.0, 200.0, 250.0)]  # value = 2500
        result = calculate_net_worth(accounts, holdings)
        assert result["assets"]["Brokerage"] == pytest.approx(2_500.0)

    def test_investment_account_balance_ignored(self):
        # Even if balance is set, only holdings value should be used
        accounts = [_account("inv_001", "Brokerage", AccountType.INVESTMENT, 99_999.0)]
        holdings = [_holding("inv_001", "VTI", 10.0, 200.0, 250.0)]  # value = 2500
        result = calculate_net_worth(accounts, holdings)
        assert result["assets"]["Brokerage"] == pytest.approx(2_500.0)

    def test_investment_account_with_no_holdings_is_zero(self):
        accounts = [_account("inv_001", "Empty Brokerage", AccountType.INVESTMENT, 0.0)]
        result = calculate_net_worth(accounts, [])
        assert result["assets"]["Empty Brokerage"] == 0.0

    def test_investment_account_with_holdings_from_another_account_is_zero(self):
        accounts = [_account("inv_001", "My Brokerage", AccountType.INVESTMENT, 0.0)]
        holdings = [_holding("inv_002", "VTI", 10.0, 200.0, 250.0)]  # different account
        result = calculate_net_worth(accounts, holdings)
        assert result["assets"]["My Brokerage"] == 0.0

    def test_investment_account_sums_multiple_holdings(self):
        accounts = [_account("inv_001", "Brokerage", AccountType.INVESTMENT, 0.0)]
        holdings = [
            _holding("inv_001", "VTI", 10.0, 200.0, 250.0),   # 2500
            _holding("inv_001", "BND", 20.0, 80.0, 75.0),     # 1500
        ]
        result = calculate_net_worth(accounts, holdings)
        assert result["assets"]["Brokerage"] == pytest.approx(4_000.0)


# ---------------------------------------------------------------------------
# Liability classification
# ---------------------------------------------------------------------------


class TestLiabilityClassification:
    def test_credit_balance_in_liabilities_as_positive(self):
        accounts = [_account("cc_001", "Visa", AccountType.CREDIT, -1_500.0)]
        result = calculate_net_worth(accounts, [])
        assert result["liabilities"]["Visa"] == pytest.approx(1_500.0)
        assert "Visa" not in result["assets"]

    def test_loan_balance_in_liabilities_as_positive(self):
        accounts = [_account("loan_001", "Auto Loan", AccountType.LOAN, -12_000.0)]
        result = calculate_net_worth(accounts, [])
        assert result["liabilities"]["Auto Loan"] == pytest.approx(12_000.0)

    def test_liability_balance_is_absolute_value(self):
        """Negative balance stored as positive in liabilities dict."""
        accounts = [_account("cc_001", "Card", AccountType.CREDIT, -3_456.78)]
        result = calculate_net_worth(accounts, [])
        assert result["liabilities"]["Card"] == pytest.approx(3_456.78)


# ---------------------------------------------------------------------------
# Net worth arithmetic
# ---------------------------------------------------------------------------


class TestNetWorthArithmetic:
    def test_net_worth_equals_assets_minus_liabilities(self):
        accounts = [
            _account("chk_001", "Checking", AccountType.DEPOSITORY, 10_000.0),
            _account("cc_001", "Credit Card", AccountType.CREDIT, -2_000.0),
        ]
        result = calculate_net_worth(accounts, [])
        assert result["net_worth"] == pytest.approx(8_000.0)
        assert result["total_assets"] == pytest.approx(10_000.0)
        assert result["total_liabilities"] == pytest.approx(2_000.0)

    def test_negative_net_worth_when_liabilities_exceed_assets(self):
        accounts = [
            _account("chk_001", "Checking", AccountType.DEPOSITORY, 1_000.0),
            _account("loan_001", "Big Loan", AccountType.LOAN, -50_000.0),
        ]
        result = calculate_net_worth(accounts, [])
        assert result["net_worth"] == pytest.approx(-49_000.0)

    def test_totals_are_sum_of_individual_values(self):
        accounts = [
            _account("chk_001", "Checking", AccountType.DEPOSITORY, 5_000.0),
            _account("sav_001", "Savings", AccountType.DEPOSITORY, 10_000.0),
            _account("cc_001", "Card A", AccountType.CREDIT, -1_000.0),
            _account("cc_002", "Card B", AccountType.CREDIT, -500.0),
        ]
        result = calculate_net_worth(accounts, [])
        assert result["total_assets"] == pytest.approx(15_000.0)
        assert result["total_liabilities"] == pytest.approx(1_500.0)
        assert result["net_worth"] == pytest.approx(13_500.0)

    def test_values_rounded_to_two_decimal_places(self):
        accounts = [_account("chk_001", "Checking", AccountType.DEPOSITORY, 1_000.005)]
        result = calculate_net_worth(accounts, [])
        # Result should be rounded to 2 decimal places
        assert result["assets"]["Checking"] == round(1_000.005, 2)


# ---------------------------------------------------------------------------
# Integration: sample data
# ---------------------------------------------------------------------------


class TestNetWorthWithSampleData:
    def test_investment_accounts_use_holdings_not_zero_balance(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        holdings = loader.load_holdings()
        result = calculate_net_worth(accounts, holdings)

        # Investment accounts have balance=0 in CSV; result must reflect holdings value
        assert result["assets"]["Fidelity Brokerage"] > 0
        assert result["assets"]["Fidelity Roth IRA"] > 0

    def test_depository_accounts_use_balance(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        holdings = loader.load_holdings()
        result = calculate_net_worth(accounts, holdings)

        assert result["assets"]["Chase Checking"] == pytest.approx(5_420.50)
        assert result["assets"]["Marcus HYSA"] == pytest.approx(28_500.00)

    def test_liabilities_are_positive_amounts(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        result = calculate_net_worth(accounts, [])

        # All liability values must be positive
        for name, value in result["liabilities"].items():
            assert value > 0, f"Liability '{name}' must be positive, got {value}"

    def test_net_worth_is_positive_for_sample_data(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        holdings = loader.load_holdings()
        result = calculate_net_worth(accounts, holdings)

        assert result["net_worth"] > 0

    def test_net_worth_arithmetic_consistency(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        holdings = loader.load_holdings()
        result = calculate_net_worth(accounts, holdings)

        assert result["net_worth"] == pytest.approx(
            result["total_assets"] - result["total_liabilities"], rel=1e-6
        )
