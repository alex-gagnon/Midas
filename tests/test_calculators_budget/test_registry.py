"""Tests for budget model registry and list_budget_models()."""

from src.calculators.budget import list_budget_models
from src.calculators.budget_models import MODELS


class TestListBudgetModels:
    def test_returns_list(self):
        assert isinstance(list_budget_models(), list)

    def test_all_six_models_present(self):
        keys = {m["key"] for m in list_budget_models()}
        assert keys == {"50_30_20", "70_20_10", "80_20", "zero_based", "60_20_20", "kakeibo"}

    def test_each_model_has_required_fields(self):
        for m in list_budget_models():
            assert "key" in m
            assert "name" in m
            assert "description" in m

    def test_matches_models_registry(self):
        assert {m["key"] for m in list_budget_models()} == set(MODELS.keys())


class TestModelRegistration:
    def test_60_20_20_registered_in_models(self):
        assert "60_20_20" in MODELS

    def test_kakeibo_registered_in_models(self):
        assert "kakeibo" in MODELS

    def test_60_20_20_model_key_matches_registry_key(self):
        assert MODELS["60_20_20"].key == "60_20_20"

    def test_kakeibo_model_key_matches_registry_key(self):
        assert MODELS["kakeibo"].key == "kakeibo"
