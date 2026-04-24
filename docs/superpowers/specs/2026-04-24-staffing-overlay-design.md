# Staffing Overlay for Total Pull Requests Chart

## Overview

Add a staffing level line to `total_pull_requests.png` to show team size alongside PR activity over time.

## Requirements

- Display monthly headcount as a stepped line on the existing PR chart
- Calculate headcount at month-end (count of developers active on the last day of each month)
- Use a secondary y-axis on the right side labeled "Resources"
- Extend x-axis to cover all months with staffing data, showing 0 PRs for months without PR data
- Orange (#FFA500) stepped line for staffing, distinct from blue PR line

## Data Source

**Excel file:** `AMAT Developer Project Duration.xlsx`

**Relevant columns:**
- `AMAT DOJ` — Date of Joining the project
- `AMAT DOD` — Date of Departure from the project

**Headcount calculation:** For each month, count developers where:
- `AMAT DOJ <= last day of month` AND
- `AMAT DOD >= last day of month`

Skip rows with null dates (e.g., the "Average" summary row).

## Architecture

### New Module: `staffing.py`

```python
def get_monthly_headcount(
    excel_path: str,
    start_month: str,  # "YYYY-MM" format
    end_month: str     # "YYYY-MM" format
) -> dict[str, int]:
    """
    Returns {month_label: headcount} where month_label is "Mon YYYY" format.
    
    Headcount is calculated at month-end.
    """
```

### Modified: `jira_info.py`

In `generate_bitbucket_charts()`:

1. Import and call `get_monthly_headcount()` — the date range is determined by:
   - Start: minimum of `created_after` parameter and earliest `AMAT DOJ` in the Excel file
   - End: current month (or latest `AMAT DOD` if in the past)
2. Merge PR months with staffing months, filling missing PR data with 0
3. Add secondary y-axis configuration
4. Add staffing trace as stepped line on secondary axis

## Chart Modifications

```python
fig4.update_layout(
    yaxis2=dict(
        title="Resources",
        overlaying="y",
        side="right",
    )
)

fig4.add_trace(
    go.Scatter(
        x=months,
        y=headcounts,
        mode="lines+markers",
        line=dict(color="#FFA500", width=2, shape="hv"),
        marker=dict(size=6),
        name="Resources",
        yaxis="y2",
    )
)
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Excel file not found | Log warning, generate chart without staffing line |
| Missing columns | Raise `KeyError` |
| Empty date range | Return empty dict |
| No active developers for a month | Return 0 for that month |

## File Changes

| File | Change |
|------|--------|
| `staffing.py` (new) | Module with `get_monthly_headcount()` function |
| `jira_info.py` | Import staffing, modify `generate_bitbucket_charts()` |

## Visual Specification

- Chart dimensions: 1200x600 (unchanged)
- PR line: Blue (#636EFA), solid with markers (unchanged)
- Staffing line: Orange (#FFA500), stepped (`shape="hv"`), with markers
- Left y-axis: "Pull Requests"
- Right y-axis: "Resources"
- Legend shows both "Pull Requests" and "Resources"
