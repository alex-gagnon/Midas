"""Unit tests for src/calculators/performance.py."""

import pytest

from src.calculators.performance import calculate_brokerage_performance
from src.models.holding import Holding


def _holding(account_id, symbol, shares, cost, price):
    return Holding(account_id, symbol, symbol, shares, cost, price)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestPerformanceReturnShape:
    def test_top_level_keys(self):
        result = calculate_brokerage_performance([])
        assert set(result.keys()) == {"filter", "summary", "positions"}

    def test_summary_keys(self):
        result = calculate_brokerage_performance([])
        assert set(result["summary"].keys()) == {
            "total_value", "total_cost_basis", "total_gain_loss",
            "total_return_pct", "position_count",
        }

    def test_position_keys(self):
        holdings = [_holding("inv_001", "VTI", 10.0, 200.0, 250.0)]
        result = calculate_brokerage_performance(holdings)
        pos = result["positions"][0]
        assert set(pos.keys()) == {
            "symbol", "name", "account_id", "shares", "current_price",
            "current_value", "cost_basis", "gain_loss", "gain_loss_pct",
            "allocation_pct",
        }


# ---------------------------------------------------------------------------
# Empty holdings
# ---------------------------------------------------------------------------


class TestEmptyHoldings:
    def test_empty_list_returns_zeros(self):
        result = calculate_brokerage_performance([])
        assert result["summary"]["total_value"] == 0.0
        assert result["summary"]["total_cost_basis"] == 0.0
        assert result["summary"]["total_gain_loss"] == 0.0
        assert result["summary"]["total_return_pct"] == 0.0
        assert result["summary"]["position_count"] == 0
        assert result["positions"] == []

    def test_empty_filter_account_id_returns_all_zero(self):
        result = calculate_brokerage_performance([], account_id="inv_001")
        assert result["summary"]["position_count"] == 0


# ---------------------------------------------------------------------------
# Account filter
# ---------------------------------------------------------------------------


class TestAccountFilter:
    def _multi_account_holdings(self):
        return [
            _holding("inv_001", "VTI", 10.0, 200.0, 250.0),
            _holding("inv_001", "BND", 5.0, 80.0, 75.0),
            _holding("ira_001", "VTI", 20.0, 180.0, 250.0),
        ]

    def test_no_filter_includes_all_holdings(self):
        holdings = self._multi_account_holdings()
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["position_count"] == 3

    def test_filter_by_account_id_excludes_others(self):
        holdings = self._multi_account_holdings()
        result = calculate_brokerage_performance(holdings, account_id="inv_001")
        assert result["summary"]["position_count"] == 2

    def test_filter_by_ira_account(self):
        holdings = self._multi_account_holdings()
        result = calculate_brokerage_performance(holdings, account_id="ira_001")
        assert result["summary"]["position_count"] == 1
        assert result["positions"][0]["symbol"] == "VTI"

    def test_filter_nonexistent_account_returns_empty(self):
        holdings = self._multi_account_holdings()
        result = calculate_brokerage_performance(holdings, account_id="nonexistent")
        assert result["summary"]["position_count"] == 0
        assert result["positions"] == []

    def test_filter_stored_in_result(self):
        result = calculate_brokerage_performance([], account_id="inv_001")
        assert result["filter"]["account_id"] == "inv_001"

    def test_no_filter_stores_none(self):
        result = calculate_brokerage_performance([])
        assert result["filter"]["account_id"] is None


# ---------------------------------------------------------------------------
# Summary calculations
# ---------------------------------------------------------------------------


class TestSummaryCalculations:
    def test_total_value(self):
        holdings = [
            _holding("inv", "A", 10.0, 100.0, 150.0),  # value=1500
            _holding("inv", "B", 5.0, 200.0, 100.0),   # value=500
        ]
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_value"] == pytest.approx(2_000.0)

    def test_total_cost_basis(self):
        holdings = [
            _holding("inv", "A", 10.0, 100.0, 150.0),  # cost=1000
            _holding("inv", "B", 5.0, 200.0, 100.0),   # cost=1000
        ]
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_cost_basis"] == pytest.approx(2_000.0)

    def test_total_gain_loss_positive(self):
        holdings = [_holding("inv", "A", 10.0, 100.0, 150.0)]  # gain=500
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_gain_loss"] == pytest.approx(500.0)

    def test_total_gain_loss_negative(self):
        holdings = [_holding("inv", "A", 10.0, 150.0, 100.0)]  # loss=-500
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_gain_loss"] == pytest.approx(-500.0)

    def test_total_return_pct(self):
        holdings = [_holding("inv", "A", 10.0, 100.0, 125.0)]
        # gain=250, cost=1000, return=25%
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_return_pct"] == pytest.approx(25.0)

    def test_total_return_pct_zero_when_no_cost(self):
        holdings = [_holding("inv", "A", 10.0, 0.0, 100.0)]
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_return_pct"] == 0.0

    def test_position_count(self):
        holdings = [
            _holding("inv", "A", 1.0, 100.0, 100.0),
            _holding("inv", "B", 1.0, 100.0, 100.0),
            _holding("inv", "C", 1.0, 100.0, 100.0),
        ]
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["position_count"] == 3


# ---------------------------------------------------------------------------
# Position details
# ---------------------------------------------------------------------------


class TestPositionDetails:
    def _single_position_result(self):
        holdings = [_holding("inv_001", "VTI", 10.0, 200.0, 250.0)]
        return calculate_brokerage_performance(holdings)

    def test_position_fields_match_holding(self):
        result = self._single_position_result()
        pos = result["positions"][0]
        assert pos["symbol"] == "VTI"
        assert pos["account_id"] == "inv_001"
        assert pos["shares"] == 10.0
        assert pos["current_price"] == pytest.approx(250.0)
        assert pos["current_value"] == pytest.approx(2_500.0)
        assert pos["cost_basis"] == pytest.approx(2_000.0)
        assert pos["gain_loss"] == pytest.approx(500.0)
        assert pos["gain_loss_pct"] == pytest.approx(25.0)

    def test_single_position_has_100pct_allocation(self):
        result = self._single_position_result()
        assert result["positions"][0]["allocation_pct"] == pytest.approx(100.0)

    def test_allocation_pcts_sum_to_100(self):
        holdings = [
            _holding("inv", "A", 10.0, 100.0, 200.0),   # value=2000
            _holding("inv", "B", 5.0, 50.0, 200.0),     # value=1000
            _holding("inv", "C", 2.0, 100.0, 500.0),    # value=1000
        ]
        result = calculate_brokerage_performance(holdings)
        total_alloc = sum(p["allocation_pct"] for p in result["positions"])
        assert total_alloc == pytest.approx(100.0, abs=0.1)

    def test_zero_total_value_gives_zero_allocation(self):
        holdings = [_holding("inv", "A", 0.0, 100.0, 200.0)]  # 0 shares → 0 value
        result = calculate_brokerage_performance(holdings)
        assert result["positions"][0]["allocation_pct"] == 0.0

    def test_positions_sorted_by_value_descending(self):
        holdings = [
            _holding("inv", "SMALL", 1.0, 100.0, 100.0),    # value=100
            _holding("inv", "LARGE", 100.0, 100.0, 100.0),  # value=10000
            _holding("inv", "MID", 10.0, 100.0, 100.0),     # value=1000
        ]
        result = calculate_brokerage_performance(holdings)
        values = [p["current_value"] for p in result["positions"]]
        assert values == sorted(values, reverse=True)


# ---------------------------------------------------------------------------
# Integration: sample data
# ---------------------------------------------------------------------------


class TestPerformanceWithSampleData:
    def test_all_holdings_loaded(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["position_count"] == len(holdings)

    def test_inv_001_filter(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings, account_id="inv_001")
        assert result["summary"]["position_count"] == 4  # VTI, VXUS, BND, AAPL

    def test_ira_001_filter(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings, account_id="ira_001")
        assert result["summary"]["position_count"] == 3  # VTI, VXUS, BND

    def test_allocation_pcts_sum_to_100_for_sample(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings)
        total = sum(p["allocation_pct"] for p in result["positions"])
        assert total == pytest.approx(100.0, abs=0.2)

    def test_positions_sorted_descending_for_sample(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings)
        values = [p["current_value"] for p in result["positions"]]
        assert values == sorted(values, reverse=True)

    def test_total_return_pct_is_non_zero(self, sample_data_dir):
        """Sample portfolio should show a real return, not accidentally zero."""
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        result = calculate_brokerage_performance(holdings)
        assert result["summary"]["total_return_pct"] != 0.0
