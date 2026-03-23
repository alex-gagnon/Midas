"""Unit tests for src/loaders/composite_loader.py."""

from pathlib import Path

import pytest

from src.loaders.composite_loader import CompositeLoader
from src.loaders.fidelity_loader import FidelityLoader
from src.loaders.qfx_loader import QFXLoader
from src.loaders.vanguard_loader import VanguardLoader

# Fixture directories
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIDELITY_CSV = FIXTURES_DIR / "Portfolio_Positions_sample.csv"
QFX_SAMPLE = FIXTURES_DIR / "sample.qfx"
QFX_INVESTMENT = FIXTURES_DIR / "sample_investment.qfx"
VANGUARD_CSV = FIXTURES_DIR / "sample_vanguard.csv"


# ---------------------------------------------------------------------------
# pytest fixtures — build isolated temp dirs for each loader
# ---------------------------------------------------------------------------


@pytest.fixture()
def fidelity_dir(tmp_path) -> Path:
    d = tmp_path / "fidelity"
    d.mkdir()
    (d / FIDELITY_CSV.name).write_bytes(FIDELITY_CSV.read_bytes())
    return d


@pytest.fixture()
def qfx_dir(tmp_path) -> Path:
    d = tmp_path / "qfx"
    d.mkdir()
    (d / QFX_SAMPLE.name).write_bytes(QFX_SAMPLE.read_bytes())
    (d / QFX_INVESTMENT.name).write_bytes(QFX_INVESTMENT.read_bytes())
    return d


@pytest.fixture()
def vanguard_dir(tmp_path) -> Path:
    d = tmp_path / "vanguard"
    d.mkdir()
    (d / VANGUARD_CSV.name).write_bytes(VANGUARD_CSV.read_bytes())
    return d


# ---------------------------------------------------------------------------
# Empty loader list
# ---------------------------------------------------------------------------


class TestCompositeLoaderEmpty:
    def test_empty_loaders_returns_no_accounts(self):
        loader = CompositeLoader([])
        assert loader.load_accounts() == []

    def test_empty_loaders_returns_no_holdings(self):
        loader = CompositeLoader([])
        assert loader.load_holdings() == []

    def test_empty_loaders_returns_no_transactions(self):
        loader = CompositeLoader([])
        assert loader.load_transactions() == []


# ---------------------------------------------------------------------------
# Aggregation across multiple loaders
# ---------------------------------------------------------------------------


class TestCompositeLoaderAggregation:
    def test_aggregates_accounts_from_multiple_loaders(self, fidelity_dir, vanguard_dir):
        composite = CompositeLoader(
            [
                FidelityLoader(fidelity_dir),
                VanguardLoader(vanguard_dir),
            ]
        )
        accounts = composite.load_accounts()
        # Fidelity fixture: 1 account; Vanguard fixture: 1 account
        assert len(accounts) == 2

    def test_aggregates_holdings_from_multiple_loaders(self, fidelity_dir, vanguard_dir):
        composite = CompositeLoader(
            [
                FidelityLoader(fidelity_dir),
                VanguardLoader(vanguard_dir),
            ]
        )
        holdings = composite.load_holdings()
        # Fidelity fixture: 2 holdings (NVDA, FSKAX); Vanguard fixture: 1 (AAPL)
        assert len(holdings) == 3

    def test_aggregates_transactions_from_multiple_loaders(self, qfx_dir, vanguard_dir):
        composite = CompositeLoader(
            [
                QFXLoader(qfx_dir),
                VanguardLoader(vanguard_dir),
            ]
        )
        # QFX loader returns at least some transactions; Vanguard fixture has 3
        qfx_txns = QFXLoader(qfx_dir).load_transactions()
        vanguard_txns = VanguardLoader(vanguard_dir).load_transactions()
        composite_txns = composite.load_transactions()
        assert len(composite_txns) == len(qfx_txns) + len(vanguard_txns)

    def test_account_ids_from_different_loaders_are_present(self, fidelity_dir, vanguard_dir):
        composite = CompositeLoader(
            [
                FidelityLoader(fidelity_dir),
                VanguardLoader(vanguard_dir),
            ]
        )
        ids = {a.account_id for a in composite.load_accounts()}
        assert "X99999999" in ids
        assert "vanguard_99999999" in ids

    def test_single_loader_behaves_identically(self, fidelity_dir):
        direct = FidelityLoader(fidelity_dir)
        composite = CompositeLoader([FidelityLoader(fidelity_dir)])
        assert len(composite.load_accounts()) == len(direct.load_accounts())
        assert len(composite.load_holdings()) == len(direct.load_holdings())
        assert len(composite.load_transactions()) == len(direct.load_transactions())
