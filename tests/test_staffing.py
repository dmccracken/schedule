import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

from staffing import get_monthly_headcount, get_staffing_date_range


def test_get_monthly_headcount_single_developer_active_all_months():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-01-01")],
        "AMAT DOD": [pd.Timestamp("2024-03-31")],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 1,
        "Feb 2024": 1,
        "Mar 2024": 1,
    }


def test_get_monthly_headcount_developer_joins_mid_range():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-02-15")],
        "AMAT DOD": [pd.Timestamp("2024-03-31")],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 0,
        "Feb 2024": 1,
        "Mar 2024": 1,
    }


def test_get_monthly_headcount_developer_leaves_mid_range():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-01-01")],
        "AMAT DOD": [pd.Timestamp("2024-02-15")],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 1,
        "Feb 2024": 0,
        "Mar 2024": 0,
    }


def test_get_monthly_headcount_multiple_developers():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-02-01"),
            pd.Timestamp("2024-01-15"),
        ],
        "AMAT DOD": [
            pd.Timestamp("2024-03-31"),
            pd.Timestamp("2024-03-31"),
            pd.Timestamp("2024-02-29"),
        ],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 2,
        "Feb 2024": 3,
        "Mar 2024": 2,
    }


def test_get_monthly_headcount_skips_null_dates():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-01-01"), pd.NaT],
        "AMAT DOD": [pd.Timestamp("2024-03-31"), pd.NaT],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 1,
        "Feb 2024": 1,
        "Mar 2024": 1,
    }


def test_get_monthly_headcount_empty_range():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-01-01")],
        "AMAT DOD": [pd.Timestamp("2024-03-31")],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-03", "2024-01")

    assert result == {}


def test_get_staffing_date_range():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [
            pd.Timestamp("2023-06-15"),
            pd.Timestamp("2024-01-01"),
        ],
        "AMAT DOD": [
            pd.Timestamp("2024-02-28"),
            pd.Timestamp("2024-12-31"),
        ],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        start, end = get_staffing_date_range("fake.xlsx")

    assert start == "2023-06"
    assert end == "2024-12"
