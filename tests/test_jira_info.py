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
