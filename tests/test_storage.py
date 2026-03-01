"""Tests for the parquet-based storage module."""

import os

import numpy as np
import pandas as pd
import pytest

from turbulence import storage


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up a temporary data directory."""
    monkeypatch.setenv('TURBULENCE_DATA_DIR', str(tmp_path))
    storage.init_data_dir()
    return tmp_path


@pytest.fixture
def sample_price_df():
    """Sample price DataFrame."""
    dates = pd.date_range('2024-01-01', periods=10, freq='B')
    return pd.DataFrame({
        'ticker': 'SPY',
        'date': dates,
        'open': np.random.uniform(400, 410, 10),
        'high': np.random.uniform(410, 420, 10),
        'low': np.random.uniform(390, 400, 10),
        'close': np.random.uniform(400, 415, 10),
        'volume': np.random.randint(50_000_000, 200_000_000, 10),
    })


@pytest.fixture
def sample_composite_df():
    """Sample composite scores DataFrame."""
    dates = pd.date_range('2024-01-01', periods=10, freq='B')
    return pd.DataFrame({
        'date': dates,
        'composite_score': np.random.uniform(0.1, 0.9, 10),
        'regime_label': np.random.choice(['low', 'normal', 'elevated'], 10),
        'vix_component': np.random.uniform(0, 1, 10),
        'vix_term_component': np.random.uniform(0, 1, 10),
        'realized_vol_component': np.random.uniform(0, 1, 10),
        'turbulence_component': np.random.uniform(0, 1, 10),
        'garch_component': np.random.uniform(0, 1, 10),
    })


class TestInitDataDir:
    def test_creates_structure(self, data_dir):
        assert (data_dir / 'prices').is_dir()

    def test_idempotent(self, data_dir):
        storage.init_data_dir()
        assert (data_dir / 'prices').is_dir()


class TestPrices:
    def test_save_and_load(self, data_dir, sample_price_df):
        storage.save_prices('SPY', sample_price_df)
        loaded = storage.load_prices('SPY')
        assert len(loaded) == 10
        assert 'close' in loaded.columns

    def test_load_missing_ticker(self, data_dir):
        df = storage.load_prices('NONEXISTENT')
        assert df.empty

    def test_date_filtering(self, data_dir, sample_price_df):
        storage.save_prices('SPY', sample_price_df)
        loaded = storage.load_prices('SPY', start_date='2024-01-07')
        assert len(loaded) < 10
        assert all(pd.to_datetime(loaded['date']) >= pd.Timestamp('2024-01-07'))

    def test_upsert_no_duplicates(self, data_dir, sample_price_df):
        storage.save_prices('SPY', sample_price_df)
        # Save again with overlapping data
        storage.save_prices('SPY', sample_price_df)
        loaded = storage.load_prices('SPY')
        assert len(loaded) == 10  # No duplicates

    def test_upsert_updates_values(self, data_dir, sample_price_df):
        storage.save_prices('SPY', sample_price_df)
        # Modify a value and re-save
        updated = sample_price_df.copy()
        updated.loc[0, 'close'] = 999.0
        storage.save_prices('SPY', updated)
        loaded = storage.load_prices('SPY')
        assert loaded.iloc[0]['close'] == 999.0

    def test_load_all_prices(self, data_dir, sample_price_df):
        storage.save_prices('SPY', sample_price_df)
        spy2 = sample_price_df.copy()
        spy2['ticker'] = 'TLT'
        storage.save_prices('TLT', spy2)

        loaded = storage.load_all_prices(['SPY', 'TLT'])
        assert len(loaded) == 20

    def test_vix_ticker_filename(self, data_dir, sample_price_df):
        vix_df = sample_price_df.copy()
        vix_df['ticker'] = '^VIX'
        storage.save_prices('^VIX', vix_df)
        loaded = storage.load_prices('^VIX')
        assert len(loaded) == 10


class TestCompositeScores:
    def test_save_and_load(self, data_dir, sample_composite_df):
        storage.save_composite_scores(sample_composite_df)
        loaded = storage.load_composite_scores()
        assert len(loaded) == 10
        assert 'composite_score' in loaded.columns

    def test_date_filtering(self, data_dir, sample_composite_df):
        storage.save_composite_scores(sample_composite_df)
        loaded = storage.load_composite_scores(start_date='2024-01-07')
        assert len(loaded) < 10

    def test_upsert(self, data_dir, sample_composite_df):
        storage.save_composite_scores(sample_composite_df)
        storage.save_composite_scores(sample_composite_df)
        loaded = storage.load_composite_scores()
        assert len(loaded) == 10

    def test_empty_load(self, data_dir):
        loaded = storage.load_composite_scores()
        assert loaded.empty


class TestRegimeClassifications:
    def test_save_and_load(self, data_dir):
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'vix_level': [15.0, 16.0, 17.0, 18.0, 19.0],
            'vix_regime': ['normal'] * 5,
        })
        storage.save_regime_classifications(df)
        loaded = storage.load_regime_classifications()
        assert len(loaded) == 5


class TestVolatilityMetrics:
    def test_save_and_load(self, data_dir):
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'garman_klass_vol': np.random.uniform(0.1, 0.3, 5),
        })
        storage.save_volatility_metrics(df)
        loaded = storage.load_volatility_metrics()
        assert len(loaded) == 5
