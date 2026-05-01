# `--new-jiras` Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--new-jiras` CLI option to list Jira issues created in the last 7 days for all components.

**Architecture:** Add a new function `list_new_jiras()` that iterates over all components, queries Jira for recently created issues, and prints a formatted console table grouped by component.

**Tech Stack:** Python, requests (existing JiraClient)

---

## File Structure

| File | Change | Purpose |
|------|--------|---------|
| `jira_info.py` | Modify | Add JQL constants, `list_new_jiras()` function, CLI argument, main handler |
| `tests/test_jira_info.py` | Create | Unit tests for `list_new_jiras()` |

---

## Task 1: Add JQL Constants

**Files:**
- Modify: `jira_info.py:1195` (after existing JQL constants)

- [ ] **Step 1: Add JQL constants for new jiras query**

Open `jira_info.py` and add these constants after line 1195 (after `COMMON_JQL_POSTFIX`):

```python
COMMON_JQL_NEW_JIRAS_PREFIX = "project = ASE AND component = "
COMMON_JQL_NEW_JIRAS_SUFFIX = " AND created >= -7d ORDER BY created DESC"
```

- [ ] **Step 2: Commit**

```bash
git add jira_info.py
git commit -m "feat: add JQL constants for --new-jiras query"
```

---

## Task 2: Create Test File with First Test

**Files:**
- Create: `tests/test_jira_info.py`

- [ ] **Step 1: Create test file with test for formatting a single issue**

Create `tests/test_jira_info.py`:

```python
"""Tests for jira_info.py"""

import sys
from io import StringIO
from unittest.mock import MagicMock

sys.path.insert(0, ".")
from jira_info import list_new_jiras


def test_list_new_jiras_formats_single_issue():
    """Test that a single issue is formatted correctly."""
    mock_client = MagicMock()
    mock_client.search_issues.return_value = {
        "total": 1,
        "issues": [
            {
                "key": "ASE-1234",
                "fields": {
                    "summary": "Add new feature",
                    "customfield_10106": 3,
                    "fixVersions": [{"name": "v1.0"}],
                },
            }
        ],
    }

    components = [
        {"component": "Test Component", "name": "Test Dashboard", "version": "v1.0"}
    ]

    captured = StringIO()
    sys.stdout = captured
    try:
        list_new_jiras(mock_client, components)
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "ASE-1234" in output
    assert "3 pts" in output
    assert "Add new feature" in output
    assert "Test Dashboard [v1.0]" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jira_info.py::test_list_new_jiras_formats_single_issue -v`

Expected: FAIL with `ImportError` or `AttributeError` (function doesn't exist yet)

- [ ] **Step 3: Commit test**

```bash
git add tests/test_jira_info.py
git commit -m "test: add failing test for list_new_jiras single issue formatting"
```

---

## Task 3: Implement list_new_jiras Function

**Files:**
- Modify: `jira_info.py:1197` (after the new JQL constants, before `ReleaseNotesParser` class)

- [ ] **Step 1: Add the list_new_jiras function**

Add this function after the JQL constants (around line 1197):

```python
def list_new_jiras(client, components):
    """
    List Jira issues created in the last 7 days for all components.

    Args:
        client: JiraClient instance
        components: List of component dictionaries from COMPONENTS

    Returns:
        None (prints to stdout)
    """
    print(f"\n{'='*80}")
    print("NEW JIRAS (Last 7 Days)")
    print(f"{'='*80}")

    total_issues = 0
    components_with_issues = 0

    for component in components:
        component_name = component["name"]
        version = component.get("version")
        jira_component = component["component"]

        jql = (
            COMMON_JQL_NEW_JIRAS_PREFIX
            + f'"{jira_component}"'
            + COMMON_JQL_NEW_JIRAS_SUFFIX
        )

        results = client.search_issues(
            jql,
            max_results=100,
            fields=["summary", "customfield_10106", "fixVersions"],
        )

        if not results:
            continue

        issues = results.get("issues", [])
        if not issues:
            continue

        components_with_issues += 1
        total_issues += len(issues)

        version_display = f"[{version}]" if version else "[No Version]"
        print(f"\n{component_name} {version_display}")
        print("-" * 80)

        for issue in issues:
            key = issue.get("key", "N/A")
            fields = issue.get("fields", {})
            summary = fields.get("summary", "No summary")
            story_points = fields.get("customfield_10106")

            if story_points is not None:
                points_display = f"{int(story_points)} pts"
            else:
                points_display = "-"

            print(f"  {key:<12} {points_display:<8} {summary}")

    print(f"\n{'-'*80}")
    if total_issues == 0:
        print("No new issues found in the last 7 days.")
    else:
        print(f"Total: {total_issues} new issues across {components_with_issues} components")
    print(f"{'='*80}")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_jira_info.py::test_list_new_jiras_formats_single_issue -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: implement list_new_jiras function"
```

---

## Task 4: Add Test for No Version Display

**Files:**
- Modify: `tests/test_jira_info.py`

- [ ] **Step 1: Add test for component without version**

Add this test to `tests/test_jira_info.py`:

```python
def test_list_new_jiras_shows_no_version_label():
    """Test that components without version show [No Version]."""
    mock_client = MagicMock()
    mock_client.search_issues.return_value = {
        "total": 1,
        "issues": [
            {
                "key": "ASE-5678",
                "fields": {
                    "summary": "Fix bug",
                    "customfield_10106": None,
                    "fixVersions": [],
                },
            }
        ],
    }

    components = [
        {"component": "Guardband", "name": "Guardband Dashboard", "version": None}
    ]

    captured = StringIO()
    sys.stdout = captured
    try:
        list_new_jiras(mock_client, components)
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "Guardband Dashboard [No Version]" in output
    assert "ASE-5678" in output
    assert "-" in output  # No story points
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_jira_info.py::test_list_new_jiras_shows_no_version_label -v`

Expected: PASS (implementation already handles this)

- [ ] **Step 3: Commit**

```bash
git add tests/test_jira_info.py
git commit -m "test: add test for no-version component display"
```

---

## Task 5: Add Test for Empty Results

**Files:**
- Modify: `tests/test_jira_info.py`

- [ ] **Step 1: Add test for no issues found**

Add this test to `tests/test_jira_info.py`:

```python
def test_list_new_jiras_handles_no_issues():
    """Test output when no new issues exist."""
    mock_client = MagicMock()
    mock_client.search_issues.return_value = {"total": 0, "issues": []}

    components = [
        {"component": "Test Component", "name": "Test Dashboard", "version": "v1.0"}
    ]

    captured = StringIO()
    sys.stdout = captured
    try:
        list_new_jiras(mock_client, components)
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "No new issues found in the last 7 days." in output
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_jira_info.py::test_list_new_jiras_handles_no_issues -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_jira_info.py
git commit -m "test: add test for empty results handling"
```

---

## Task 6: Add CLI Argument

**Files:**
- Modify: `jira_info.py:2449` (after `--include-commits` argument)

- [ ] **Step 1: Add --new-jiras argument**

Add this argument after the `--include-commits` argument (around line 2449):

```python
    parser.add_argument(
        "--new-jiras",
        action="store_true",
        help="List Jira issues created in the last 7 days for all components",
    )
```

- [ ] **Step 2: Commit**

```bash
git add jira_info.py
git commit -m "feat: add --new-jiras CLI argument"
```

---

## Task 7: Add Main Handler

**Files:**
- Modify: `jira_info.py:2490` (after `args.generate_release_notes` block, before `args.developer_velocity` block)

- [ ] **Step 1: Add handler for --new-jiras in main()**

Add this block after the `generate_release_notes` handler (after line 2490, before the `developer_velocity` check):

```python
    # List new jiras if requested
    if args.new_jiras:
        print("\nFetching new Jira issues from the last 7 days...")
        list_new_jiras(client, COMPONENTS)
        sys.exit(0)
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/test_jira_info.py -v`

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add --new-jiras handler in main()"
```

---

## Task 8: Manual Integration Test

**Files:**
- None (manual test)

- [ ] **Step 1: Verify help text**

Run: `python jira_info.py --help`

Expected: `--new-jiras` appears in help output with description "List Jira issues created in the last 7 days for all components"

- [ ] **Step 2: Test with real Jira (if credentials available)**

Run: `python jira_info.py -u <jira-url> -U <username> -P <password> --new-jiras --no-verify-ssl`

Expected: Output shows component headers with version, issue keys, story points, and summaries grouped by component.

- [ ] **Step 3: Final commit with all changes verified**

```bash
git status
```

Expected: Working tree clean (all changes committed)

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Add JQL constants | - |
| 2 | Create test file, first test | 1 test |
| 3 | Implement `list_new_jiras()` | - |
| 4 | Test no-version display | 1 test |
| 5 | Test empty results | 1 test |
| 6 | Add CLI argument | - |
| 7 | Add main handler | - |
| 8 | Manual integration test | - |

**Total: 3 unit tests, 7 commits**
