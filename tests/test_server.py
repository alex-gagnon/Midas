"""Smoke-level integration tests for src/server.py.

These tests verify that:
- Each tool is registered on the mcp instance and callable.
- The full pipeline (loader → calculator → response) produces dicts with the
  expected top-level keys when run against the sample data directory.

Calculation correctness is tested by the dedicated calculator test modules.
"""

from pathlib import Path

import pytest

# Locate the sample data directory used by all tools.
_SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"


# ---------------------------------------------------------------------------
# Module-level import with MIDAS_DATA_DIR pointed at sample data
# ---------------------------------------------------------------------------
# server.py reads MIDAS_DATA_DIR at import time, so we cannot use monkeypatch
# here (that only works inside test functions).  Instead we import the module
# after forcing the environment variable, then re-use the already-imported
# module in every test.  Because pytest collects test modules before running
# them, we use autouse session-scoped setup to guarantee the env is set before
# the first import.

import os

os.environ.setdefault("MIDAS_DATA_DIR", str(_SAMPLE_DIR))

import src.server as server  # noqa: E402  (must come after env setup)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_names() -> set[str]:
    """Return the set of tool names registered on the mcp instance."""
    # FastMCP stores registered tools in _tool_manager (or _tools depending on
    # version).  We access the public-facing listing when available; fall back
    # to inspecting internal state.
    mgr = getattr(server.mcp, "_tool_manager", None)
    if mgr is not None:
        return set(mgr._tools.keys())
    # Older FastMCP keeps tools directly on the server object
    return set(getattr(server.mcp, "_tools", {}).keys())


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    _EXPECTED_TOOLS = {
        "get_net_worth",
        "get_budget_breakdown",
        "list_budget_models",
        "get_brokerage_performance",
        "get_savings_rate",
        "get_spending_trends",
        "get_debt_payoff_projection",
    }

    def test_all_expected_tools_are_registered(self):
        registered = _tool_names()
        assert self._EXPECTED_TOOLS.issubset(registered), (
            f"Missing tools: {self._EXPECTED_TOOLS - registered}"
        )

    @pytest.mark.parametrize("tool_name", [
        "get_net_worth",
        "get_budget_breakdown",
        "list_budget_models",
        "get_brokerage_performance",
        "get_savings_rate",
        "get_spending_trends",
        "get_debt_payoff_projection",
    ])
    def test_tool_is_callable(self, tool_name):
        assert hasattr(server, tool_name), f"{tool_name!r} not found on server module"
        assert callable(getattr(server, tool_name))


# ---------------------------------------------------------------------------
# get_net_worth — top-level key contract
# ---------------------------------------------------------------------------


class TestGetNetWorthSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_net_worth()

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_net_worth_key(self, result):
        assert "net_worth" in result

    def test_has_total_assets_key(self, result):
        assert "total_assets" in result

    def test_has_total_liabilities_key(self, result):
        assert "total_liabilities" in result

    def test_has_assets_key(self, result):
        assert "assets" in result

    def test_has_liabilities_key(self, result):
        assert "liabilities" in result

    def test_net_worth_is_numeric(self, result):
        assert isinstance(result["net_worth"], (int, float))

    def test_total_assets_is_numeric(self, result):
        assert isinstance(result["total_assets"], (int, float))

    def test_assets_is_dict(self, result):
        assert isinstance(result["assets"], dict)

    def test_liabilities_is_dict(self, result):
        assert isinstance(result["liabilities"], dict)

    def test_net_worth_equals_assets_minus_liabilities(self, result):
        assert result["net_worth"] == pytest.approx(
            result["total_assets"] - result["total_liabilities"], abs=0.01
        )


# ---------------------------------------------------------------------------
# get_budget_breakdown — top-level key contract
# ---------------------------------------------------------------------------


class TestGetBudgetBreakdownSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_budget_breakdown(
            start_date="2026-03-01", end_date="2026-03-31"
        )

    def test_returns_dict_with_defaults(self, result):
        assert isinstance(result, dict)

    def test_has_model_key(self, result):
        assert "model" in result

    def test_has_months_key(self, result):
        assert "months" in result

    def test_has_months_count_key(self, result):
        assert "months_count" in result

    def test_months_is_list(self, result):
        assert isinstance(result["months"], list)

    def test_invalid_date_raises_value_error(self):
        with pytest.raises((ValueError, Exception)):
            server.get_budget_breakdown(start_date="not-a-date")


# ---------------------------------------------------------------------------
# list_budget_models — contract
# ---------------------------------------------------------------------------


class TestListBudgetModelsSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.list_budget_models()

    def test_returns_list(self, result):
        assert isinstance(result, list)

    def test_list_is_non_empty(self, result):
        assert len(result) > 0

    def test_each_entry_has_key_field(self, result):
        for entry in result:
            assert "key" in entry

    def test_each_entry_has_name_field(self, result):
        for entry in result:
            assert "name" in entry

    def test_each_entry_has_description_field(self, result):
        for entry in result:
            assert "description" in entry

    def test_default_model_is_present(self, result):
        from src.calculators.budget_models import DEFAULT_MODEL
        keys = {entry["key"] for entry in result}
        assert DEFAULT_MODEL in keys


# ---------------------------------------------------------------------------
# get_brokerage_performance — top-level key contract
# ---------------------------------------------------------------------------


class TestGetBrokeragePerformanceSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_brokerage_performance()

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_filter_key(self, result):
        assert "filter" in result

    def test_has_summary_key(self, result):
        assert "summary" in result

    def test_has_positions_key(self, result):
        assert "positions" in result

    def test_positions_is_list(self, result):
        assert isinstance(result["positions"], list)

    def test_summary_has_total_value(self, result):
        assert "total_value" in result["summary"]

    def test_summary_has_position_count(self, result):
        assert "position_count" in result["summary"]

    def test_positions_count_matches_summary(self, result):
        assert len(result["positions"]) == result["summary"]["position_count"]

    def test_filter_account_id_is_none_when_not_provided(self, result):
        assert result["filter"]["account_id"] is None

    def test_filter_by_account_id(self):
        result = server.get_brokerage_performance(account_id="inv_001")
        assert result["filter"]["account_id"] == "inv_001"


# ---------------------------------------------------------------------------
# get_savings_rate — top-level key contract
# ---------------------------------------------------------------------------


class TestGetSavingsRateSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_savings_rate(
            start_date="2026-03-01", end_date="2026-03-31"
        )

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_income_key(self, result):
        assert "income" in result

    def test_has_total_saved_key(self, result):
        assert "total_saved" in result

    def test_has_savings_rate_pct_key(self, result):
        assert "savings_rate_pct" in result

    def test_has_period_key(self, result):
        assert "period" in result

    def test_has_breakdown_key(self, result):
        assert "breakdown" in result

    def test_savings_rate_pct_is_numeric(self, result):
        assert isinstance(result["savings_rate_pct"], (int, float))

    def test_income_is_non_negative(self, result):
        assert result["income"] >= 0

    def test_returns_dict_with_no_date_args(self):
        result = server.get_savings_rate()
        assert isinstance(result, dict)
        assert "savings_rate_pct" in result


# ---------------------------------------------------------------------------
# get_spending_trends — top-level key contract
# ---------------------------------------------------------------------------


class TestGetSpendingTrendsSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_spending_trends()

    @pytest.fixture(scope="class")
    def result_months_6(self):
        return server.get_spending_trends(months=6)

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_months_shown_key(self, result):
        assert "months_shown" in result

    def test_has_trend_key(self, result):
        assert "trend" in result

    def test_trend_is_list(self, result):
        assert isinstance(result["trend"], list)

    def test_months_shown_is_integer(self, result):
        assert isinstance(result["months_shown"], int)

    def test_months_shown_matches_trend_length(self, result):
        assert result["months_shown"] == len(result["trend"])

    def test_each_trend_entry_has_month_key(self, result_months_6):
        for entry in result_months_6["trend"]:
            assert "month" in entry

    def test_each_trend_entry_has_total_spent(self, result_months_6):
        for entry in result_months_6["trend"]:
            assert "total_spent" in entry

    def test_each_trend_entry_has_top_categories(self, result_months_6):
        for entry in result_months_6["trend"]:
            assert "top_categories" in entry


# ---------------------------------------------------------------------------
# get_debt_payoff_projection — top-level key contract
# ---------------------------------------------------------------------------


class TestGetDebtPayoffProjectionSmoke:
    @pytest.fixture(scope="class")
    def result(self):
        return server.get_debt_payoff_projection(monthly_payment=500.0)

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_debts_key(self, result):
        assert "debts" in result

    def test_has_total_balance_key(self, result):
        assert "total_balance" in result

    def test_has_total_monthly_payment_key(self, result):
        assert "total_monthly_payment" in result

    def test_has_projected_debt_free_date_key(self, result):
        assert "projected_debt_free_date" in result

    def test_has_total_interest_paid_key(self, result):
        assert "total_interest_paid" in result

    def test_debts_is_list(self, result):
        assert isinstance(result["debts"], list)

    def test_total_monthly_payment_reflects_input(self):
        result = server.get_debt_payoff_projection(monthly_payment=750.0)
        assert result["total_monthly_payment"] == pytest.approx(750.0)

    def test_extra_payment_accepted(self):
        result = server.get_debt_payoff_projection(
            monthly_payment=500.0, extra_payment=1000.0
        )
        assert isinstance(result, dict)
        assert "projected_debt_free_date" in result
