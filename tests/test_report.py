"""Tests for the report generation module."""

import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from turbulence.report import (
    generate_report,
    _compute_regime_periods,
    _regime_css_class,
)


class TestRegimePeriods:
    def test_basic(self):
        dates = pd.date_range('2024-01-01', periods=10, freq='B')
        regimes = pd.Series(
            ['low'] * 4 + ['normal'] * 3 + ['elevated'] * 3,
            index=dates,
        )
        periods = _compute_regime_periods(regimes)
        assert len(periods) == 3
        assert periods.iloc[0]['regime'] == 'low'
        assert periods.iloc[1]['regime'] == 'normal'
        assert periods.iloc[2]['regime'] == 'elevated'

    def test_single_regime(self):
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        regimes = pd.Series(['low'] * 5, index=dates)
        periods = _compute_regime_periods(regimes)
        assert len(periods) == 1

    def test_empty(self):
        periods = _compute_regime_periods(pd.Series(dtype=object))
        assert len(periods) == 0


class TestRegimeCssClass:
    def test_classes(self):
        assert _regime_css_class('low') == 'regime-low'
        assert _regime_css_class('extreme') == 'regime-extreme'
        assert _regime_css_class('') == ''


class TestGenerateReport:
    def test_generates_html(self, tmp_path):
        """Test report generation with mock storage."""
        dates = pd.date_range('2024-01-01', periods=50, freq='B')
        rows = []
        for d in dates:
            score = np.random.uniform(0.2, 0.6)
            regime = 'low' if score < 0.25 else ('normal' if score < 0.5 else 'elevated')
            rows.append({
                'date': d,
                'composite_score': score,
                'regime_label': regime,
                'vix_component': score * 0.3,
                'realized_vol_component': score * 0.2,
                'turbulence_component': score * 0.25,
                'garch_component': score * 0.15,
                'vix_term_component': score * 0.1,
            })

        mock_df = pd.DataFrame(rows)
        output_path = str(tmp_path / 'report.html')

        with patch('turbulence.report.storage') as mock_storage:
            mock_storage.load_composite_scores.return_value = mock_df

            result = generate_report(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 3, 31),
                output_path=output_path,
                format='html',
                include_charts=False,
            )

        assert os.path.exists(result)
        with open(result) as f:
            html = f.read()
        assert 'Turbulence Analysis Report' in html
        assert 'Executive Summary' in html
        assert 'Regime Timeline' in html
        assert 'Trading Recommendations' in html

    def test_pdf_raises_without_weasyprint(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'weasyprint':
                raise ImportError("No module named 'weasyprint'")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            with pytest.raises(ValueError, match="weasyprint"):
                generate_report(
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 3, 31),
                    output_path='test.pdf',
                    format='pdf',
                )

    def test_no_data_raises(self):
        with patch('turbulence.report.storage') as mock_storage:
            mock_storage.load_composite_scores.return_value = pd.DataFrame()

            with pytest.raises(ValueError, match="No composite score data"):
                generate_report(
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 3, 31),
                    output_path='test.html',
                )
