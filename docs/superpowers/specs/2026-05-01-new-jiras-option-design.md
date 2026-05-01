# Design: `--new-jiras` Option for jira_info.py

## Overview

Add a `--new-jiras` command-line option to `jira_info.py` that discovers Jira issues created in the last 7 days for all versioned components.

## Command Line Interface

### New Argument

```
--new-jiras    List Jira issues created in the last 7 days for versioned components
```

### Usage

```bash
python jira_info.py -u https://jira.company.com -U username -P password --new-jiras
```

## Implementation

### JQL Query

For each component in `COMPONENTS` where `version` is not null:

```sql
project = ASE AND component = "<component>" AND created >= -7d ORDER BY created DESC
```

### Fields Retrieved

| Field | Purpose |
|-------|---------|
| `key` | Jira issue number (e.g., ASE-1234) |
| `summary` | Issue description |
| `customfield_10106` | Story points |
| `fixVersion` | Fix version (for display) |

### Component Filtering

- Only components with `version != null` are queried
- Skipped components: Guardband, EPD Dashboard, PdM Dashboard

### Output Format

Console table grouped by component:

```
================================================================================
NEW JIRAS (Last 7 Days)
================================================================================

Alarm Dashboard [Alarm_26.01]
--------------------------------------------------------------------------------
  ASE-1234    3 pts    Add new alarm notification feature
  ASE-1235    5 pts    Fix dashboard loading issue
  
AutoUVA Dashboard [AUTO_UVA_26.05]
--------------------------------------------------------------------------------
  ASE-1240    2 pts    Update trace segmentation algorithm
  ASE-1241    -        Improve error handling (no estimate)

--------------------------------------------------------------------------------
Total: 4 new issues across 2 components
================================================================================
```

**Output rules:**
- Components with no new issues are omitted
- Story points show "-" if not set
- Summary line shows total count and component count
- If no new issues exist across all components, display: "No new issues found in the last 7 days."

## Code Changes

### Location

All changes in `jira_info.py`:

1. **Argument parser** (~line 2450): Add `--new-jiras` argument
2. **New function** `list_new_jiras()`: Query and display new issues
3. **Main function** (~line 2475): Handle `--new-jiras` flag, call new function and exit

### New Function Signature

```python
def list_new_jiras(client, components):
    """
    List Jira issues created in the last 7 days for versioned components.
    
    Args:
        client: JiraClient instance
        components: List of component dictionaries from COMPONENTS
    
    Returns:
        None (prints to stdout)
    """
```

### JQL Constant

Add new constant alongside existing JQL prefixes:

```python
COMMON_JQL_NEW_JIRAS_PREFIX = "project = ASE AND component = "
COMMON_JQL_NEW_JIRAS_SUFFIX = " AND created >= -7d ORDER BY created DESC"
```

## Constraints

- Lookback period is fixed at 7 days (not configurable)
- Output format is console table only (no CSV option)
- Only versioned components are queried
