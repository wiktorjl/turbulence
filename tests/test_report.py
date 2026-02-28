"""Tests for the report generation module."""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

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
    def test_generates_html(self):
        """Test report generation with mock database."""
        dates = pd.date_range('2024-01-01', periods=50, freq='B')
        rows = []
        for d in dates:
            score = np.random.uniform(0.2, 0.6)
            regime = 'low' if score < 0.25 else ('normal' if score < 0.5 else 'elevated')
            rows.append((
                d.date(), score, regime,
                score * 0.3, score * 0.2, score * 0.25,
                score * 0.15, score * 0.1,
            ))

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.description = [
            ('date',), ('composite_score',), ('regime_label',),
            ('vix_component',), ('realized_vol_component',), ('turbulence_component',),
            ('garch_component',), ('vix_term_component',),
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.get_connection.return_value = mock_conn

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = f.name

        try:
            result = generate_report(
                db=mock_db,
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
        finally:
            os.unlink(output_path)

    def test_pdf_raises(self):
        mock_db = MagicMock()
        with pytest.raises(ValueError, match="weasyprint"):
            generate_report(
                db=mock_db,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 3, 31),
                output_path='test.pdf',
                format='pdf',
            )

    def test_no_data_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.get_connection.return_value = mock_conn

        with pytest.raises(ValueError, match="No composite score data"):
            generate_report(
                db=mock_db,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 3, 31),
                output_path='test.html',
            )
