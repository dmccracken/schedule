# Staffing Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a staffing headcount line to `total_pull_requests.png` showing team size over time on a secondary y-axis.

**Architecture:** New `staffing.py` module calculates monthly headcount from Excel data. `jira_info.py` imports this module and adds a stepped orange line on a secondary y-axis to the existing PR chart.

**Tech Stack:** Python, pandas, plotly

---

## File Structure

| File | Responsibility |
|------|----------------|
| `staffing.py` (new) | Read Excel, calculate month-end headcount for a date range |
| `tests/test_staffing.py` (new) | Unit tests for headcount calculation |
| `jira_info.py` (modify) | Import staffing module, add secondary y-axis and staffing trace to fig4 |

---

### Task 1: Create staffing module with get_monthly_headcount()

**Files:**
- Create: `staffing.py`
- Create: `tests/test_staffing.py`

- [ ] **Step 1: Create tests directory**

```bash
mkdir -p tests
```

- [ ] **Step 2: Write the failing test for basic headcount calculation**

Create `tests/test_staffing.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_staffing.py::test_get_monthly_headcount_single_developer_active_all_months -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'staffing'"

- [ ] **Step 4: Write minimal staffing.py implementation**

Create `staffing.py`:

```python
import pandas as pd
from datetime import datetime
import calendar


def get_monthly_headcount(
    excel_path: str,
    start_month: str,
    end_month: str,
) -> dict[str, int]:
    """
    Calculate month-end headcount from Excel staffing data.

    Args:
        excel_path: Path to Excel file with AMAT DOJ and AMAT DOD columns
        start_month: Start month in "YYYY-MM" format
        end_month: End month in "YYYY-MM" format

    Returns:
        Dict mapping month labels ("Mon YYYY") to headcount at month-end
    """
    df = pd.read_excel(excel_path)

    df = df.dropna(subset=["AMAT DOJ", "AMAT DOD"])

    df["AMAT DOJ"] = pd.to_datetime(df["AMAT DOJ"])
    df["AMAT DOD"] = pd.to_datetime(df["AMAT DOD"])

    start_date = datetime.strptime(start_month, "%Y-%m")
    end_date = datetime.strptime(end_month, "%Y-%m")

    result = {}
    current = start_date

    while current <= end_date:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = datetime(current.year, current.month, last_day)

        count = ((df["AMAT DOJ"] <= month_end) & (df["AMAT DOD"] >= month_end)).sum()

        month_label = current.strftime("%b %Y")
        result[month_label] = int(count)

        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

    return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_staffing.py::test_get_monthly_headcount_single_developer_active_all_months -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add staffing.py tests/test_staffing.py
git commit -m "feat: add staffing module with get_monthly_headcount()"
```

---

### Task 2: Add tests for edge cases

**Files:**
- Modify: `tests/test_staffing.py`

- [ ] **Step 1: Write test for developer joining mid-range**

Add to `tests/test_staffing.py`:

```python
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
```

- [ ] **Step 2: Write test for developer leaving mid-range**

Add to `tests/test_staffing.py`:

```python
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
```

- [ ] **Step 3: Write test for multiple developers with overlapping tenure**

Add to `tests/test_staffing.py`:

```python
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
            pd.Timestamp("2024-02-28"),
        ],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-01", "2024-03")

    assert result == {
        "Jan 2024": 2,
        "Feb 2024": 3,
        "Mar 2024": 2,
    }
```

- [ ] **Step 4: Write test for skipping null dates**

Add to `tests/test_staffing.py`:

```python
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
```

- [ ] **Step 5: Write test for empty date range**

Add to `tests/test_staffing.py`:

```python
def test_get_monthly_headcount_empty_range():
    mock_df = pd.DataFrame({
        "AMAT DOJ": [pd.Timestamp("2024-01-01")],
        "AMAT DOD": [pd.Timestamp("2024-03-31")],
    })

    with patch("pandas.read_excel", return_value=mock_df):
        result = get_monthly_headcount("fake.xlsx", "2024-03", "2024-01")

    assert result == {}
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `pytest tests/test_staffing.py -v`

Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add tests/test_staffing.py
git commit -m "test: add edge case tests for staffing headcount calculation"
```

---

### Task 3: Add helper function to get staffing date range from Excel

**Files:**
- Modify: `staffing.py`
- Modify: `tests/test_staffing.py`

- [ ] **Step 1: Write failing test for get_staffing_date_range**

Add to `tests/test_staffing.py`:

```python
from staffing import get_monthly_headcount, get_staffing_date_range


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_staffing.py::test_get_staffing_date_range -v`

Expected: FAIL with "ImportError: cannot import name 'get_staffing_date_range'"

- [ ] **Step 3: Implement get_staffing_date_range**

Add to `staffing.py` after `get_monthly_headcount`:

```python
def get_staffing_date_range(excel_path: str) -> tuple[str, str]:
    """
    Get the earliest and latest dates from staffing data.

    Args:
        excel_path: Path to Excel file with AMAT DOJ and AMAT DOD columns

    Returns:
        Tuple of (start_month, end_month) in "YYYY-MM" format
    """
    df = pd.read_excel(excel_path)

    df = df.dropna(subset=["AMAT DOJ", "AMAT DOD"])

    df["AMAT DOJ"] = pd.to_datetime(df["AMAT DOJ"])
    df["AMAT DOD"] = pd.to_datetime(df["AMAT DOD"])

    earliest = df["AMAT DOJ"].min()
    latest = df["AMAT DOD"].max()

    return earliest.strftime("%Y-%m"), latest.strftime("%Y-%m")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_staffing.py::test_get_staffing_date_range -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add staffing.py tests/test_staffing.py
git commit -m "feat: add get_staffing_date_range() helper"
```

---

### Task 4: Integrate staffing overlay into jira_info.py chart

**Files:**
- Modify: `jira_info.py:2261-2299`

- [ ] **Step 1: Add import for staffing module at top of jira_info.py**

Find the imports section (around line 1-20) and add:

```python
from staffing import get_monthly_headcount, get_staffing_date_range
```

- [ ] **Step 2: Modify Chart 4 section to include staffing overlay**

Replace lines 2261-2299 (the Chart 4 section) with:

```python
    # --- Chart 4: Total Pull Requests by Month with Staffing Overlay ---
    # Build PR totals data, excluding current month
    pr_months = []
    pr_totals = []
    pr_month_to_total = {}
    for period_start in sorted(monthly_pr_totals.keys()):
        period_date = datetime.strptime(period_start, "%Y-%m-%d")
        if period_date >= current_month_start:
            continue
        month_label = period_date.strftime("%b %Y")
        pr_months.append(month_label)
        pr_totals.append(monthly_pr_totals[period_start])
        pr_month_to_total[month_label] = monthly_pr_totals[period_start]

    # Try to load staffing data
    staffing_data = {}
    try:
        staffing_start, staffing_end = get_staffing_date_range("AMAT Developer Project Duration.xlsx")
        
        pr_start = datetime.strptime(created_after, "%Y-%m-%d").strftime("%Y-%m") if created_after else None
        
        if pr_start and pr_start < staffing_start:
            combined_start = pr_start
        else:
            combined_start = staffing_start
        
        current_month = datetime.now().strftime("%Y-%m")
        if staffing_end > current_month:
            combined_end = current_month
        else:
            combined_end = staffing_end
        
        staffing_data = get_monthly_headcount(
            "AMAT Developer Project Duration.xlsx",
            combined_start,
            combined_end,
        )
    except FileNotFoundError:
        print("Warning: AMAT Developer Project Duration.xlsx not found, skipping staffing overlay")
    except Exception as e:
        print(f"Warning: Could not load staffing data: {e}")

    if pr_months or staffing_data:
        all_months = set(pr_months) | set(staffing_data.keys())
        all_months_sorted = sorted(all_months, key=lambda m: datetime.strptime(m, "%b %Y"))
        
        final_pr_totals = [pr_month_to_total.get(m, 0) for m in all_months_sorted]
        final_headcounts = [staffing_data.get(m, 0) for m in all_months_sorted]

        fig4 = go.Figure()
        
        fig4.add_trace(
            go.Scatter(
                x=all_months_sorted,
                y=final_pr_totals,
                mode="lines+markers+text",
                text=final_pr_totals,
                textposition="top center",
                texttemplate="%{text:.0f}",
                line=dict(color="#636EFA", width=2),
                marker=dict(size=8),
                name="Pull Requests",
            )
        )

        if staffing_data:
            fig4.add_trace(
                go.Scatter(
                    x=all_months_sorted,
                    y=final_headcounts,
                    mode="lines+markers",
                    line=dict(color="#FFA500", width=2, shape="hv"),
                    marker=dict(size=6),
                    name="Resources",
                    yaxis="y2",
                )
            )

        layout_config = dict(
            title=f"Total Pull Requests by Month {date_range}",
            xaxis_tickangle=-45,
            xaxis_title="Month",
            yaxis_title="Pull Requests",
            font=dict(size=12),
            width=1200,
            height=600,
        )
        
        if staffing_data:
            layout_config["yaxis2"] = dict(
                title="Resources",
                overlaying="y",
                side="right",
            )
            layout_config["legend"] = dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            )

        fig4.update_layout(**layout_config)

        fig4.write_image("total_pull_requests.png")
        print("Generated: total_pull_requests.png")
```

- [ ] **Step 3: Verify syntax is correct**

Run: `python -m py_compile jira_info.py`

Expected: No output (successful compilation)

- [ ] **Step 4: Commit**

```bash
git add jira_info.py
git commit -m "feat: add staffing overlay to total_pull_requests.png chart"
```

---

### Task 5: Manual verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 2: Generate chart with test data (if BitBucket credentials available)**

Run: `python jira_info.py --bitbucket-insights` (with appropriate credentials)

Or create a minimal test script to verify chart generation:

```python
import plotly.graph_objects as go
from staffing import get_monthly_headcount, get_staffing_date_range

start, end = get_staffing_date_range("AMAT Developer Project Duration.xlsx")
print(f"Staffing range: {start} to {end}")

headcount = get_monthly_headcount("AMAT Developer Project Duration.xlsx", start, end)
print(f"Headcount data: {headcount}")
```

- [ ] **Step 3: Visually inspect total_pull_requests.png**

Verify:
- Orange stepped line appears on chart
- Right y-axis shows "Resources" label
- Legend shows both "Pull Requests" and "Resources"
- X-axis covers all months with staffing data

- [ ] **Step 4: Commit any final adjustments if needed**

```bash
git status
# If changes needed, commit them
```
