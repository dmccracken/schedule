import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

from staffing import get_monthly_headcount


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
