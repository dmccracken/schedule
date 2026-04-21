#!/usr/bin/env python3
"""
Jira Data Center REST API component Tool

This program queries Jira Data Center using REST API with authentication
provided via command line parameters and executes predefined queries.
"""

import argparse
import requests
import json
import sys
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth


class BitBucketClient:
    """Client for interacting with BitBucket Data Center REST API"""

    def __init__(self, username, password, verify_ssl=True):
        """
        Initialize BitBucket client

        Args:
            username: BitBucket username
            password: BitBucket password or API token
            verify_ssl: Whether to verify SSL certificates
        """
        self.auth = HTTPBasicAuth(username, password)
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = verify_ssl

        if not verify_ssl:
            # Suppress SSL warnings when verification is disabled
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get_file_content(self, url, max_retries=3):
        """
        Get file content from BitBucket with retry logic for rate limiting

        Args:
            url: Full URL to the file in BitBucket
            max_retries: Maximum number of retry attempts for 429 errors

        Returns:
            File content as string, or None on error
        """
        # Convert browse URL to raw content URL
        raw_url = url.replace("/browse/", "/raw/")

        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(raw_url)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                # Handle rate limiting with exponential backoff
                if e.response is not None and e.response.status_code == 429:
                    if attempt < max_retries:
                        wait_time = (2**attempt) * 2  # 2, 4, 8 seconds
                        print(
                            f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...",
                            file=sys.stderr,
                        )
                        time.sleep(wait_time)
                        continue
                print(f"Error fetching file from BitBucket: {e}", file=sys.stderr)
                return None

        return None

    def get_all_commits(self, project_key, repo_slug, since_date, max_retries=3):
        """
        Get all commits from a repository since a given date

        Args:
            project_key: BitBucket project key (e.g., 'FSSRPT')
            repo_slug: Repository slug name
            since_date: Date string (YYYY-MM-DD) to filter commits
            max_retries: Maximum number of retry attempts for 429 errors

        Returns:
            List of commit dictionaries with author, date, message, and id
        """
        from datetime import datetime

        base_url = "https://apg-bb.amat.com"
        url = f"{base_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/commits"

        # Convert since_date to timestamp (milliseconds)
        since_dt = datetime.strptime(since_date, "%Y-%m-%d")
        since_timestamp = int(since_dt.timestamp() * 1000)

        for attempt in range(max_retries + 1):
            try:
                commits = []
                start = 0
                limit = 100

                while True:
                    params = {"limit": limit, "start": start}
                    response = self.session.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()

                    for commit in data.get("values", []):
                        commit_timestamp = commit.get("authorTimestamp", 0)

                        # Stop if we've gone past our date range
                        if commit_timestamp < since_timestamp:
                            return commits

                        commits.append({
                            "id": commit.get("id"),
                            "author": commit.get("author", {}).get("displayName", "Unknown"),
                            "email": commit.get("author", {}).get("emailAddress", ""),
                            "date": commit_timestamp,
                            "message": commit.get("message", ""),
                        })

                    if data.get("isLastPage", True):
                        break
                    start = data.get("nextPageStart", start + limit)

                return commits

            except requests.exceptions.RequestException as e:
                if e.response is not None and e.response.status_code == 429:
                    if attempt < max_retries:
                        wait_time = (2**attempt) * 2
                        print(
                            f"Rate limited on {repo_slug}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...",
                            file=sys.stderr,
                        )
                        time.sleep(wait_time)
                        continue
                print(f"Error fetching commits from {repo_slug}: {e}", file=sys.stderr)
                return []

        return []

    def get_commit_diff_stats(self, project_key, repo_slug, commit_id, max_retries=3):
        """
        Get diff statistics for a specific commit

        Args:
            project_key: BitBucket project key (e.g., 'FSSRPT')
            repo_slug: Repository slug name
            commit_id: The commit hash
            max_retries: Maximum number of retry attempts for 429 errors

        Returns:
            Dict with lines_added, lines_deleted, files_changed
        """
        base_url = "https://apg-bb.amat.com"
        url = f"{base_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/commits/{commit_id}/diff"

        for attempt in range(max_retries + 1):
            try:
                params = {"contextLines": 0, "withComments": "false"}
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                lines_added = 0
                lines_deleted = 0
                files_changed = set()

                for diff in data.get("diffs", []):
                    # Track file paths
                    dest = diff.get("destination", {})
                    if dest:
                        files_changed.add(dest.get("toString", ""))

                    # Count lines from hunks
                    for hunk in diff.get("hunks", []):
                        for segment in hunk.get("segments", []):
                            segment_type = segment.get("type", "")
                            line_count = len(segment.get("lines", []))
                            if segment_type == "ADDED":
                                lines_added += line_count
                            elif segment_type == "REMOVED":
                                lines_deleted += line_count

                return {
                    "lines_added": lines_added,
                    "lines_deleted": lines_deleted,
                    "files_changed": list(files_changed),
                }

            except requests.exceptions.RequestException as e:
                if e.response is not None and e.response.status_code == 429:
                    if attempt < max_retries:
                        wait_time = (2**attempt) * 2
                        time.sleep(wait_time)
                        continue
                # Return zeros on error rather than failing
                return {"lines_added": 0, "lines_deleted": 0, "files_changed": []}

        return {"lines_added": 0, "lines_deleted": 0, "files_changed": []}

    def get_commits_for_issue(self, project_key, repo_slug, issue_key, max_retries=3):
        """
        Get commits related to a specific Jira issue with retry logic for rate limiting

        Args:
            project_key: BitBucket project key (e.g., 'FSSRPT')
            repo_slug: Repository slug name
            issue_key: Jira issue key (e.g., 'ASE-1234')
            max_retries: Maximum number of retry attempts for 429 errors

        Returns:
            List of commit dictionaries with author and date info
        """
        # BitBucket Data Center REST API endpoint for commits
        base_url = "https://apg-bb.amat.com"
        url = (
            f"{base_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/commits"
        )

        for attempt in range(max_retries + 1):
            try:
                commits = []
                start = 0
                limit = 100

                while True:
                    params = {"limit": limit, "start": start}
                    response = self.session.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()

                    for commit in data.get("values", []):
                        # Check if commit message contains the issue key
                        message = commit.get("message", "")
                        if issue_key in message:
                            commits.append(
                                {
                                    "id": commit.get("id"),
                                    "author": commit.get("author", {}).get(
                                        "displayName", "Unknown"
                                    ),
                                    "date": commit.get("authorTimestamp"),
                                    "message": message,
                                }
                            )

                    # Check if there are more results
                    if data.get("isLastPage", True):
                        break
                    start = data.get("nextPageStart", start + limit)

                return commits

            except requests.exceptions.RequestException as e:
                # Handle rate limiting with exponential backoff
                if e.response is not None and e.response.status_code == 429:
                    if attempt < max_retries:
                        wait_time = (2**attempt) * 2  # 2, 4, 8 seconds
                        print(
                            f"Rate limited on commits for {issue_key}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...",
                            file=sys.stderr,
                        )
                        time.sleep(wait_time)
                        continue
                # For other errors or exhausted retries, print and return empty
                print(f"Error fetching commits for {issue_key}: {e}", file=sys.stderr)
                return []

        return []


class JiraClient:
    """Client for interacting with Jira Data Center REST API"""

    def __init__(self, base_url, username, password, verify_ssl=True):
        """
        Initialize Jira client

        Args:
            base_url: Base URL of Jira instance (e.g., https://jira.company.com)
            username: Jira username
            password: Jira password or API token
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = verify_ssl

        if not verify_ssl:
            # Suppress SSL warnings when verification is disabled
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def test_connection(self):
        """Test connection to Jira and return server info"""
        try:
            url = urljoin(self.base_url, "/rest/api/2/serverInfo")
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jira: {e}", file=sys.stderr)
            return None

    def search_issues(self, jql, max_results=5000, fields=None):
        """
        Search for issues using JQL

        Args:
            jql: JQL component string
            max_results: Maximum number of results to return
            fields: List of fields to return (None for default fields)

        Returns:
            Dictionary containing search results
        """
        url = urljoin(self.base_url, "/rest/api/2/search")

        params = {"jql": jql, "maxResults": max_results}

        if fields:
            params["fields"] = ",".join(fields)

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error executing component: {e}", file=sys.stderr)
            return None

    def get_issue_details(self, issue_key):
        """
        Get detailed information about a specific issue

        Args:
            issue_key: Jira issue key (e.g., 'ASE-1234')

        Returns:
            Dictionary containing issue details including created and resolved dates
        """
        url = urljoin(self.base_url, f"/rest/api/2/issue/{issue_key}")

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            fields = data.get("fields", {})
            created = fields.get("created")
            resolutiondate = fields.get("resolutiondate")
            assignee = fields.get("assignee", {})
            issue_type = fields.get("issuetype", {})

            return {
                "key": issue_key,
                "created": created,
                "resolved": resolutiondate,
                "assignee": assignee.get("displayName") if assignee else None,
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
                "type": issue_type.get("name"),
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issue {issue_key}: {e}", file=sys.stderr)
            return None

    def search_issues_with_changelog(self, jql, max_results=1000):
        """
        Search for issues and include changelog in results for transition history

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return

        Returns:
            List of issues with their changelogs
        """
        url = urljoin(self.base_url, "/rest/api/2/search")
        all_issues = []
        start_at = 0
        batch_size = min(100, max_results)  # Jira limits to 100 with expand

        while start_at < max_results:
            params = {
                "jql": jql,
                "maxResults": batch_size,
                "startAt": start_at,
                "expand": "changelog",
                "fields": "summary,status,assignee,created,resolutiondate,customfield_10106,issuetype",
            }

            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                issues = data.get("issues", [])
                all_issues.extend(issues)

                total = data.get("total", 0)
                if start_at + len(issues) >= total or len(issues) == 0:
                    break

                start_at += len(issues)
                print(
                    f"  Fetched {len(all_issues)}/{min(total, max_results)} issues...",
                    file=sys.stderr,
                )

            except requests.exceptions.RequestException as e:
                print(f"Error searching issues with changelog: {e}", file=sys.stderr)
                break

        return all_issues


def format_issue_output(issue):
    """Format a single issue for display"""
    key = issue.get("key", "N/A")
    fields = issue.get("fields", {})
    summary = fields.get("summary", "No summary")
    status = fields.get("status", {}).get("name", "N/A")
    priority = fields.get("priority", {}).get("name", "N/A")
    assignee = fields.get("assignee", {})
    assignee_name = (
        assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
    )

    return f"  [{key}] {summary}\n    Status: {status} | Priority: {priority} | Assignee: {assignee_name}"


def extract_story_points_data(results, print_jira_issues=False):
    """Extract story points, issue key, and component from results"""
    story_points_data = []

    if not results:
        return story_points_data

    issues = results.get("issues", [])

    for issue in issues:
        key = issue.get("key", "N/A")
        fields = issue.get("fields", {})

        # Story points field (customfield_10106)
        story_points = fields.get("customfield_10106")

        # Get components (product categories)
        components = fields.get("components", [])
        component_names = (
            [comp.get("name", "N/A") for comp in components]
            if components
            else ["No Component"]
        )

        story_points_data.append(
            {
                "key": key,
                "story_points": story_points if story_points is not None else "Not Set",
                "components": ", ".join(component_names),
            }
        )

        if print_jira_issues:
            print(f"{key} {', '.join(component_names)}: {fields.get('summary', '')}")

    return story_points_data


def calculate_resolution_time(created_str, resolved_str):
    """
    Calculate resolution time in days between created and resolved dates

    Args:
        created_str: ISO format datetime string
        resolved_str: ISO format datetime string

    Returns:
        Number of days (float), or None if dates are invalid
    """
    if not created_str or not resolved_str:
        return None

    try:
        # Parse ISO format datetime strings
        # Handle timezone offsets like -0800 by converting to -08:00 format
        created_clean = created_str.replace("Z", "+00:00")
        resolved_clean = resolved_str.replace("Z", "+00:00")

        # Handle timezone format like -0800 (convert to -08:00)
        tz_pattern = r"([+-]\d{2})(\d{2})$"
        created_clean = re.sub(tz_pattern, r"\1:\2", created_clean)
        resolved_clean = re.sub(tz_pattern, r"\1:\2", resolved_clean)

        created = datetime.fromisoformat(created_clean)
        resolved = datetime.fromisoformat(resolved_clean)
        delta = resolved - created
        return delta.total_seconds() / (24 * 3600)  # Convert to days
    except (ValueError, AttributeError) as e:
        # Silently handle date parsing errors (common with various date formats)
        return None


def parse_jira_date(date_str):
    """
    Parse Jira date string to datetime object

    Args:
        date_str: ISO format datetime string from Jira

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Handle timezone offsets like -0800 by converting to -08:00 format
        date_clean = date_str.replace("Z", "+00:00")
        tz_pattern = r"([+-]\d{2})(\d{2})$"
        date_clean = re.sub(tz_pattern, r"\1:\2", date_clean)
        return datetime.fromisoformat(date_clean)
    except (ValueError, AttributeError):
        return None


def extract_transition_dates(changelog, resolution_date_str, initial_assignee=None):
    """
    Extract In Progress and Closed transition dates from issue changelog,
    along with the assignee at the time of the In Progress transition.

    Args:
        changelog: Changelog object from Jira issue (with 'histories' key)
        resolution_date_str: Resolution date string to use if no In Progress found
        initial_assignee: The initial assignee from issue creation (fallback)

    Returns:
        Dictionary with 'in_progress_date', 'closed_date' as datetime objects,
        'in_progress_assignee' as string (display name), and 'assignee_history'
        as list of all assignees in chronological order
    """
    in_progress_date = None
    closed_date = None
    in_progress_assignee = None

    # Track current assignee as we process changelog chronologically
    current_assignee = initial_assignee

    # Track full assignee history (chronological order)
    assignee_history = []
    if initial_assignee:
        assignee_history.append(initial_assignee)

    histories = changelog.get("histories", []) if changelog else []

    for history in histories:
        history_date = parse_jira_date(history.get("created"))
        items = history.get("items", [])

        # First pass: update assignee if changed in this history entry
        for item in items:
            if item.get("field") == "assignee":
                current_assignee = item.get("toString")  # New assignee name
                if current_assignee and current_assignee not in assignee_history:
                    assignee_history.append(current_assignee)

        # Second pass: check for status transitions
        for item in items:
            if item.get("field") == "status":
                to_status = item.get("toString", "").lower()

                # Find first transition TO an "in progress" type status
                # Match common status names indicating work has started
                in_progress_statuses = [
                    "in progress",
                    "inprogress",
                    "in development",
                    "development",
                    "active",
                    "in review",
                    "code review",
                    "testing",
                    "in testing",
                ]
                if in_progress_date is None and to_status in in_progress_statuses:
                    in_progress_date = history_date
                    in_progress_assignee = current_assignee

                # Find transition TO "Closed"
                if to_status == "closed":
                    closed_date = history_date

    # Track whether we actually found an In Progress transition
    had_in_progress = in_progress_date is not None

    # If no In Progress transition found, use resolution date (zero duration)
    if in_progress_date is None and closed_date is not None:
        in_progress_date = closed_date
        in_progress_assignee = current_assignee  # Use final assignee as fallback
    elif in_progress_date is None:
        # Fallback to resolution date if available
        in_progress_date = parse_jira_date(resolution_date_str)
        in_progress_assignee = current_assignee

    return {
        "in_progress_date": in_progress_date,
        "closed_date": closed_date,
        "in_progress_assignee": in_progress_assignee,
        "had_in_progress": had_in_progress,
        "assignee_history": assignee_history,
    }


def find_last_valid_developer(assignee_history, valid_developers, testers):
    """
    Find the last valid developer from assignee history.

    Args:
        assignee_history: List of assignees in chronological order
        valid_developers: List of valid developer base names (without --CNTR)
        testers: List of tester names to exclude

    Returns:
        The last valid developer name from history, or None if not found
    """
    import re

    # Search history in reverse to find last valid developer
    for assignee in reversed(assignee_history):
        if not assignee:
            continue

        # Check if this is a tester (skip)
        is_tester = False
        for tester in testers:
            if re.search(re.escape(tester), assignee, re.IGNORECASE):
                is_tester = True
                break

        if is_tester:
            continue

        # Check if this matches a valid developer (ignoring --CNTR suffix)
        for dev in valid_developers:
            if re.search(re.escape(dev), assignee, re.IGNORECASE):
                return assignee

    return None


def get_velocity_period(date_obj):
    """
    Calculate the calendar month period for a given date

    Args:
        date_obj: datetime object

    Returns:
        Tuple of (period_start, period_end) as date strings (YYYY-MM-DD)
    """
    if date_obj is None:
        return None, None

    import calendar

    # Get just the date part (remove timezone info)
    if hasattr(date_obj, "date"):
        date_only = date_obj.date()
    else:
        date_only = date_obj

    # Get first day of the month
    period_start = date_only.replace(day=1)

    # Get last day of the month
    last_day = calendar.monthrange(date_only.year, date_only.month)[1]
    period_end = date_only.replace(day=last_day)

    return period_start.strftime("%Y-%m-%d"), period_end.strftime("%Y-%m-%d")


def normalize_name(name):
    """
    Normalize a developer name for comparison.

    Args:
        name: Developer display name

    Returns:
        Normalized lowercase name with suffixes removed
    """
    if not name:
        return ""
    name = name.lower().strip()
    name = name.replace(" --cntr", "")
    name = name.replace("--cntr", "")
    return name


def match_developer(author_name, valid_developers, testers):
    """
    Match a BitBucket author to a valid developer.

    Args:
        author_name: BitBucket commit author display name
        valid_developers: List of valid developer names
        testers: List of tester names to exclude

    Returns:
        Matched developer name, or None if no match or is a tester
    """
    import re

    if not author_name:
        return None

    # Check if author is a tester (exclude)
    for tester in testers:
        if re.search(re.escape(tester), author_name, re.IGNORECASE):
            return None

    normalized = normalize_name(author_name)

    # Try exact match first
    for dev in valid_developers:
        if normalize_name(dev) == normalized:
            return dev

    # Try partial match (substring in either direction)
    for dev in valid_developers:
        dev_normalized = normalize_name(dev)
        if normalized in dev_normalized or dev_normalized in normalized:
            return dev

    return None


def classify_rework(commit_author, commit_date, file_path, file_history, jira_issue_type, rework_window_days=30):
    """
    Classify rework signals for a commit touching a specific file.

    Args:
        commit_author: Normalized author name of current commit
        commit_date: Datetime of current commit
        file_path: Path of file being analyzed
        file_history: Dict mapping file_path to list of (author, date) tuples
        jira_issue_type: Issue type from Jira if commit references an issue, else None
        rework_window_days: Number of days to look back for rework detection

    Returns:
        Dict of rework signals (all boolean)
    """
    from datetime import timedelta

    signals = {
        "file_churn": False,
        "same_author": False,
        "cross_author": False,
        "bug_fix": False,
    }

    # Check if this is a bug fix based on Jira issue type
    if jira_issue_type and jira_issue_type.lower() == "defect":
        signals["bug_fix"] = True

    # Get recent commits to this file within the rework window
    recent_commits = []
    if file_path in file_history:
        cutoff_date = commit_date - timedelta(days=rework_window_days)
        for author, date in file_history[file_path]:
            if date >= cutoff_date and date < commit_date:
                recent_commits.append((author, date))

    # File churn: 3+ touches to same file within window (this would be the 3rd+)
    if len(recent_commits) >= 2:
        signals["file_churn"] = True

    # Same-author rework: developer modified their own recent code
    if any(author == commit_author for author, _ in recent_commits):
        signals["same_author"] = True

    # Cross-author rework: developer modified someone else's recent code
    if any(author != commit_author for author, _ in recent_commits):
        signals["cross_author"] = True

    return signals


def generate_release_notes_table(
    jira_client, bitbucket_client, components, include_commit_details=False
):
    """
    Generate release notes table for all components

    Args:
        jira_client: JiraClient instance
        bitbucket_client: BitBucketClient instance
        components: List of component dictionaries
        include_commit_details: Whether to fetch commit counts and resolution times

    Returns:
        CSV formatted table as string
    """
    parser = ReleaseNotesParser()
    table_data = []

    for idx, component in enumerate(components):
        if not component.get("release_notes"):
            continue

        component_name = component["name"]
        version = component.get("version", "N/A")
        release_notes_url = component["release_notes"]

        print(f"Processing {component_name}...")

        # Add a small delay between components to avoid rate limiting
        if idx > 0:
            time.sleep(1)

        # Fetch release notes content
        content = bitbucket_client.get_file_content(release_notes_url)
        if not content:
            print(f"  Could not fetch release notes for {component_name}")
            continue

        # Parse release notes
        releases = parser.parse_release_notes(content)
        if not releases:
            print(f"  No releases found in release notes for {component_name}")
            continue

        # Extract repository info from URL
        # URL format: https://apg-bb.amat.com/projects/FSSRPT/repos/alarm_dispatch/browse/...
        url_parts = release_notes_url.split("/")
        project_key = url_parts[4]  # FSSRPT
        repo_slug = url_parts[6]  # alarm_dispatch

        # Process each release
        for release in releases:
            release_tag = release["tag"]
            enhancements = release["enhancements"]
            defects = release["defects"]

            print(
                f"  Release {release_tag}: {len(enhancements)} enhancements, {len(defects)} defects"
            )

            # Collect all issues
            all_issues = enhancements + defects

            total_commits = 0
            resolution_times = []
            developers = set()

            # Track actual issue types from Jira for validation
            jira_enhancements = 0
            jira_defects = 0
            mismatches = []

            # Process each issue
            for issue_key in all_issues:
                # Get issue details from Jira
                issue_details = jira_client.get_issue_details(issue_key)
                if issue_details:
                    # Validate issue type against release notes categorization
                    issue_type = issue_details.get("type", "")
                    is_defect_in_jira = issue_type == "Defect"
                    is_defect_in_notes = issue_key in defects

                    if is_defect_in_jira:
                        jira_defects += 1
                    else:
                        jira_enhancements += 1

                    # Check for mismatch
                    if is_defect_in_jira != is_defect_in_notes:
                        category_in_notes = (
                            "Defect" if is_defect_in_notes else "Enhancement"
                        )
                        mismatches.append(
                            f"{issue_key} (Jira type: {issue_type}, Release notes: {category_in_notes})"
                        )

                    # Optionally calculate resolution time
                    if include_commit_details:
                        res_time = calculate_resolution_time(
                            issue_details.get("created"), issue_details.get("resolved")
                        )
                        if res_time is not None:
                            resolution_times.append(res_time)

                # Optionally get commits from BitBucket
                if include_commit_details:
                    commits = bitbucket_client.get_commits_for_issue(
                        project_key, repo_slug, issue_key
                    )
                    total_commits += len(commits)

                    # Track developers
                    for commit in commits:
                        developers.add(commit.get("author", "Unknown"))

            # Verify counts and log warnings if there are discrepancies
            if jira_enhancements != len(enhancements) or jira_defects != len(defects):
                print(
                    f"  WARNING: Mismatch in {component_name} release {release_tag}:",
                    file=sys.stderr,
                )
                print(
                    f"    Release notes: {len(enhancements)} enhancements, {len(defects)} defects",
                    file=sys.stderr,
                )
                print(
                    f"    Jira issue types: {jira_enhancements} enhancements, {jira_defects} defects",
                    file=sys.stderr,
                )
                if mismatches:
                    print(f"    Mismatched issues:", file=sys.stderr)
                    for mismatch in mismatches:
                        print(f"      {mismatch}", file=sys.stderr)

            # Calculate average resolution time
            avg_resolution = (
                sum(resolution_times) / len(resolution_times) if resolution_times else 0
            )

            # Add to table data using actual Jira counts
            table_data.append(
                {
                    "component": component_name,
                    "version": version,
                    "release_tag": release_tag,
                    "enhancements": jira_enhancements,
                    "defects": jira_defects,
                    "commits": total_commits,
                    "avg_resolution_days": avg_resolution,
                    "developers": (
                        ", ".join(sorted(developers)) if developers else "N/A"
                    ),
                }
            )

    # Generate CSV file
    if not table_data:
        return "No release notes data found."

    csv = "Component,Version,Release Tag,Enhancements,Defects,Total Commits,Time to Resolve (days)\n"

    for row in table_data:
        csv += f"{row['component']},{row['version']},{row['release_tag']},"
        csv += f"{row['enhancements']},{row['defects']},{row['commits']},"
        csv += f"{row['avg_resolution_days']:.1f}\n"

    return csv


def print_story_points_summary(
    all_story_points_data, query_description="", details=False
):
    if details:
        """Print a formatted summary of story points across all queries"""
        print(f"\n{'='*80}")
        print(f"{query_description} STORY POINTS SUMMARY")
        print(f"{'='*80}\n")

        # Print header
        print(f"{'Jira Key':<15} {'Story Points':<15} {'Product Category'}")
        print(f"{'-'*15} {'-'*15} {'-'*40}")

    total_points = 0
    issues_with_points = 0
    component_totals = {}  # Track story points by component

    for data in all_story_points_data:
        key = data["key"]
        points = data["story_points"]
        components = data["components"]

        # Format story points for display
        points_display = str(points) if points != "Not Set" else "Not Set"

        if details:
            print(f"{key:<15} {points_display:<15} {components}")

        # Calculate totals
        if points != "Not Set":
            points_value = float(points)
            total_points += points_value
            issues_with_points += 1

            # Track by component
            if components not in component_totals:
                component_totals[components] = {"points": 0, "count": 0}
            component_totals[components]["points"] += points_value
            component_totals[components]["count"] += 1
        else:
            # Ensure component is tracked even if no points
            if components not in component_totals:
                component_totals[components] = {"points": 0, "count": 0}
            component_totals[components]["count"] += 1  # Count issue even if no points

    # Print component totals
    print(f"\n{'-'*80}")
    print(f"{query_description} STORY POINTS BY COMPONENT")
    print(f"{'-'*80}")
    for component in sorted(component_totals.keys()):
        comp_data = component_totals[component]
        points_str = f"{comp_data['points']:.1f} points"
        issues_str = f"({comp_data['count']} issues)"
        print(f"{component:<40} {points_str:>12} {issues_str}")

    # Print summary statistics
    print(f"\n{'-'*80}")
    print(f"Total Issues: {len(all_story_points_data)}")
    print(f"Issues with Story Points: {issues_with_points}")
    print(f"Total Story Points: {total_points}")
    if issues_with_points > 0:
        print(f"Average Story Points: {total_points / issues_with_points:.2f}")
    print(f"{'='*80}")


def print_component_results(component_name, results, query_description=""):
    """Print formatted component results"""
    print(f"\n{'='*80}")
    print(f"component: {component_name}")
    print(f"{'='*80}")

    if not results:
        print("  Error retrieving results")
        return

    total = results.get("total", 0)
    issues = results.get("issues", [])

    print(f"Total {query_description}results: {total}")
    print(f"Showing: {len(issues)} issue(s)\n")

    if not issues:
        print("  No issues found")
    else:
        for issue in issues:
            print(format_issue_output(issue))
            print()


# Common JQL prefix for all queries
COMPONENTS = [
    {
        "component": "Alarms Dashboard",
        "name": "Alarm Dashboard",
        "version": "Alarm_26.01",
        "release_notes": "https://apg-bb.amat.com/projects/FSSRPT/repos/alarm_dispatch/browse/Alarm_Comprehensive_Service/scripts/ReleaseNotes.txt",
    },
    {
        "component": "AutoUVA",
        "name": "AutoUVA Dashboard",
        "version": "AUTO_UVA_26.05",
        "release_notes": "https://apg-bb.amat.com/projects/FSSRPT/repos/trace_segmentation/browse/Auto_Uva_Comprehensive_Service/scripts/ReleaseNotes.txt",
    },
    {
        "component": "CSV",
        "name": "CSV Dashboard",
        "version": "CSV_26.01",
        "release_notes": "https://apg-bb.amat.com/projects/FSSRPT/repos/csv/browse/CSV_Comprehensive_Service/scripts/ReleaseNotes.txt",
    },
    {
        "component": "DES",
        "name": "DES Dashboard",
        "version": "DES_V26.05",
        #"version": "DES_V2",
        "release_notes": None,
    },
    # {
    #     "component": "Everest",
    #     "name": "Everest Dashboard",
    #     "version": "Everest_V2",
    #     "release_notes": None,
    # },
    {
        "component": "PPTS",
        "name": "PPTS Dashboard",
        #"version": "PPTS_26.03",
        "version": "PPTS_26.07",
        "release_notes": "https://apg-bb.amat.com/projects/FSSRPT/repos/pts_dashboard/browse/ReleaseNotes.txt",
    },
    {
        "component": "ToolConnection",
        "name": "ToolConnection Dashboard",
        "version": "Toolconnection2.0",
        "release_notes": None,
    },
    {
        "component": "Guardband",
        "name": "Guardband Dashboard",
        "version": None,
        "release_notes": None,
    },
    {
        "component": "EPD Dashboard",
        "name": "EPD Dashboard",
        "version": None,
        "release_notes": None,
    },
    {
        "component": "PdM Dashboard",
        "name": "PdM Dashboard",
        "version": None,
        "release_notes": None,
    },
]

# BitBucket repositories for developer insights
BITBUCKET_REPOS = [
    {"project": "FSSRPT", "slug": "des", "name": "DES"},
    {"project": "FSSRPT", "slug": "csv", "name": "CSV"},
    {"project": "FSSRPT", "slug": "trace_segmentation", "name": "Trace Segmentation"},
    {"project": "FSSRPT", "slug": "alarm_dispatch", "name": "Alarm Dispatch"},
    {"project": "FSSRPT", "slug": "tool_connection_control_app", "name": "Tool Connection"},
    {"project": "FSSRPT", "slug": "pts_dashboard", "name": "PTS Dashboard"},
]

COMMON_JQL_BACKLOG_PREFIX = (
    "project = ASE and status = new and fixVersion is EMPTY and component ="
)
COMMON_JQL_ACTIVE_RELEASE_PREFIX = "project = ASE and status != CLOSED and component = "
COMMON_JQL_TOTAL_RELEASE_PREFIX = "project = ASE and component = "
COMMON_JQL_ACTIVE_RELEASE_VERSION = " AND fixVersion = "
COMMON_JQL_ACTIVE_RELEASE_FILTER = " and status != Closed and status != DUPLICATE and status != REJECTED and status != VERIFICATION "
COMMON_JQL_POSTFIX = " ORDER BY Rank ASC"


class ReleaseNotesParser:
    """Parser for release notes files"""

    def __init__(self):
        # Pattern to match release tags (e.g., #Tag 26.01.01, # Tag 25.12.01)
        self.release_tag_pattern = re.compile(r"^#\s*[Tt]ag\s+(\d+\.\d+(?:\.\d+)?)")
        # Pattern to match Jira issue keys (e.g., ASE-1234)
        self.jira_issue_pattern = re.compile(r"\b(ASE-\d+)\b")

    def parse_release_notes(self, content):
        """
        Parse release notes content and extract structured data

        Args:
            content: Release notes file content as string

        Returns:
            List of dictionaries containing release tag data
        """
        if not content:
            return []

        releases = []
        current_release = None
        current_section = None

        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Check if this line is a release tag (e.g., #Tag 26.01.01)
            tag_match = self.release_tag_pattern.match(line)
            if tag_match:
                # Save previous release if exists
                if current_release:
                    releases.append(current_release)

                # Start new release
                current_release = {
                    "tag": tag_match.group(1),  # Extract version number
                    "enhancements": [],
                    "defects": [],
                }
                current_section = None
                continue

            if not current_release:
                continue

            # Check for section headers (lines starting with * or containing keywords)
            line_lower = line.lower()
            if line.startswith("*") or line.startswith("-") or line.startswith("•"):
                # Check what type of section this is
                if "enhancement" in line_lower:
                    current_section = "enhancements"
                    continue
                elif (
                    "bug" in line_lower or "fix" in line_lower or "defect" in line_lower
                ):
                    current_section = "defects"
                    continue

            # If no explicit section header found, default to defects for bug fixes
            if (
                current_section is None
                and line
                and (line.startswith("-") or line.startswith("*"))
            ):
                # Default to defects if no section specified
                current_section = "defects"

            # Extract Jira issues from the line
            if line:
                issues = self.jira_issue_pattern.findall(line)
                for issue_key in issues:
                    # Add to current section if specified, otherwise to defects
                    section = current_section if current_section else "defects"
                    if issue_key not in current_release[section]:
                        current_release[section].append(issue_key)

        # Don't forget the last release
        if current_release:
            releases.append(current_release)

        return releases


def execute_component_queries(
    client,
    components,
    jql_prefix,
    query_description,
    max_results,
    story_points_summary,
    use_version=False,
    include_active_filter=False,
    print_queries=False,
    print_jira_issues=False,
):
    """
    Execute Jira queries for all components and collect results

    Args:
        client: JiraClient instance
        components: List of component dictionaries
        jql_prefix: JQL query prefix
        query_description: Description of the query type (e.g., "BACKLOG", "ACTIVE RELEASE")
        max_results: Maximum number of results per query
        story_points_summary: Whether to show story points summary
        use_version: Whether to filter by version (and skip components without version)
        include_active_filter: Whether to include active release status filter

    Returns:
        List of story points data dictionaries
    """
    story_points_data = []

    for component in components:
        # Skip components without version if version is required
        if use_version and component["version"] is None:
            continue

        component_name = component["name"]

        # Build JQL query
        jql = jql_prefix + f' "{component["component"]}"'

        if include_active_filter:
            jql += COMMON_JQL_ACTIVE_RELEASE_FILTER

        if use_version:
            jql += COMMON_JQL_ACTIVE_RELEASE_VERSION + f' "{component["version"]}"'

        jql += COMMON_JQL_POSTFIX

        if print_queries:
            print(f"{jql}")

        # Execute query
        results = client.search_issues(jql, max_results=max_results)

        # Process results
        if story_points_summary:
            component_story_points = extract_story_points_data(
                results, print_jira_issues=print_jira_issues
            )
            story_points_data.extend(component_story_points)
        else:
            print_component_results(
                component_name, results, query_description=query_description
            )

    # Print summary if requested
    if story_points_summary:
        print_story_points_summary(
            story_points_data, query_description=query_description
        )

    return story_points_data


def calculate_developer_velocity(jira_client, created_after, output_file):
    """
    Calculate developer velocity (story points per month) for closed issues

    Args:
        jira_client: JiraClient instance
        created_after: Date string (YYYY-MM-DD) to filter issues created on or after
        output_file: Path to output CSV file

    Returns:
        None (writes results to CSV file)
    """
    from datetime import timedelta
    from collections import defaultdict

    # Build JQL query for closed issues
    jql = f'project = ASE AND status = Closed AND created >= "{created_after}" ORDER BY created ASC'
    print(f"Executing JQL: {jql}")

    # Fetch issues with changelog
    issues = jira_client.search_issues_with_changelog(jql)
    print(f"Found {len(issues)} closed issues")

    # Track velocity data per month: {(developer, period_start, period_end): {issues, points}}
    velocity_data = defaultdict(lambda: {"issues": 0, "total_points": 0})
    skipped_no_points = 0
    skipped_no_in_progress = 0
    skipped_no_assignee = 0
    skipped_no_dates = 0

    # Collect all unique status transitions for debugging
    all_status_values = set()

    # Debug: track issues attributed to specific people for investigation
    debug_names = ["Allen Lai", "Henrik Schneider", "Michael Olstad"]
    debug_issues = []

    # Testers and excluded people should not be credited with development work (story points)
    testers = ["Allen Lai", "Henrik Schneider", "Michael Olstad", "Ryan Patz",
               "Dennis", "Ramyaa", "Pavithra", "Tannu", "Lundi", "Minal", "Prajwal"]

    # Valid developers (contractors) who should be credited
    valid_developers = [
        "Hemalatha Mallala",
        "Hemalatha Nallanna Gari",
        "NAGARAJ B S",
        "Roshini Jayalakshmi",
        "SNEHA HA",
        "Shashivardhan Manne",
    ]

    # Track issues reassigned from testers to developers
    reassigned_issues = []
    skipped_no_valid_developer = 0

    for issue in issues:
        key = issue.get("key", "N/A")
        fields = issue.get("fields", {})

        # Get story points (skip if none)
        story_points = fields.get("customfield_10106")
        if story_points is None or story_points == 0:
            skipped_no_points += 1
            continue

        # Get initial assignee as fallback for changelog parsing
        assignee_obj = fields.get("assignee")
        initial_assignee = assignee_obj.get("displayName") if assignee_obj else None

        # Extract transition dates and assignee at In Progress time from changelog
        changelog = issue.get("changelog", {})
        resolution_date = fields.get("resolutiondate")

        # Collect all status values for debugging
        for history in changelog.get("histories", []):
            for item in history.get("items", []):
                if item.get("field") == "status":
                    all_status_values.add(item.get("toString", "").lower())

        transition_dates = extract_transition_dates(changelog, resolution_date, initial_assignee)

        # Skip issues that never went through "In Progress" status
        # (these are often QA/testing tasks, not development work)
        if not transition_dates.get("had_in_progress", False):
            skipped_no_in_progress += 1
            continue

        in_progress_date = transition_dates["in_progress_date"]
        closed_date = transition_dates["closed_date"]

        # Use assignee at In Progress time (the developer who worked on it)
        developer = transition_dates["in_progress_assignee"]
        if not developer:
            skipped_no_assignee += 1
            continue

        # Check if the developer is a tester - if so, find last valid developer from history
        import re
        is_tester = any(re.search(re.escape(t), developer, re.IGNORECASE) for t in testers)

        if is_tester:
            assignee_history = transition_dates.get("assignee_history", [])
            valid_developer = find_last_valid_developer(assignee_history, valid_developers, testers)

            if valid_developer:
                reassigned_issues.append({
                    "key": key,
                    "original": developer,
                    "reassigned_to": valid_developer,
                    "story_points": story_points,
                    "history": assignee_history,
                })
                developer = valid_developer
            else:
                # No valid developer found in history - skip this issue
                skipped_no_valid_developer += 1
                continue

        # Debug: capture details for specific people
        if any(name in (developer or "") for name in debug_names):
            debug_issues.append({
                "key": key,
                "developer": developer,
                "initial_assignee": initial_assignee,
                "had_in_progress": transition_dates.get("had_in_progress", False),
                "story_points": story_points,
            })

        # Skip if we can't determine dates
        if closed_date is None:
            skipped_no_dates += 1
            continue

        # Get monthly period based on closed date
        period_start, period_end = get_velocity_period(closed_date)
        if period_start is None:
            skipped_no_dates += 1
            continue

        # Aggregate data
        group_key = (developer, period_start, period_end)
        velocity_data[group_key]["issues"] += 1
        velocity_data[group_key]["total_points"] += float(story_points)

    print(f"\nProcessing summary:")
    print(f"  Issues with valid data: {sum(v['issues'] for v in velocity_data.values())}")
    print(f"  Skipped (no story points): {skipped_no_points}")
    print(f"  Skipped (no In Progress transition): {skipped_no_in_progress}")
    print(f"  Skipped (no assignee): {skipped_no_assignee}")
    print(f"  Skipped (no valid dates): {skipped_no_dates}")
    print(f"  Skipped (tester with no developer in history): {skipped_no_valid_developer}")
    print(f"  Reassigned from tester to developer: {len(reassigned_issues)}")

    # Show reassignment details
    if reassigned_issues:
        print(f"\n  Reassigned issues:")
        for ri in reassigned_issues:
            print(f"    - {ri['key']}: {ri['original']} -> {ri['reassigned_to']} ({ri['story_points']} pts)")

    # Show all unique status values found (helps identify missing status names)
    if all_status_values:
        print(f"\n  All status values found in changelogs:")
        for status in sorted(all_status_values):
            print(f"    - {status}")

    # Debug output for testers
    if debug_issues:
        print(f"\n{'='*80}")
        print(f"DEBUG: Issues attributed to {debug_names}")
        print(f"{'='*80}")
        for di in debug_issues:
            print(f"  {di['key']}: attributed to '{di['developer']}'")
            print(f"    - Initial assignee: {di['initial_assignee']}")
            print(f"    - Had In Progress transition: {di['had_in_progress']}")
            print(f"    - Story points: {di['story_points']}")
        print(f"{'='*80}")
        print(f"Total issues attributed to these names: {len(debug_issues)}")
        no_in_progress = sum(1 for di in debug_issues if not di['had_in_progress'])
        print(f"Issues WITHOUT In Progress transition: {no_in_progress}")
        print(f"{'='*80}\n")

    # Generate chart instead of CSV
    import plotly.express as px
    import numpy as np
    from datetime import datetime

    # Get current month to exclude incomplete data
    current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Build data for chart
    chart_data = []

    for group_key, data in velocity_data.items():
        developer, period_start, period_end = group_key

        # Skip current month (incomplete)
        period_date = datetime.strptime(period_start, "%Y-%m-%d")
        if period_date >= current_month_start:
            continue

        # Clean up developer name (remove --CNTR suffix for display)
        display_name = developer.replace(" --CNTR", "")

        # Format month for display (e.g., "Jan 2026")
        month_label = period_date.strftime("%b %Y")

        chart_data.append({
            "Developer": display_name,
            "Month": month_label,
            "Story Points": data["total_points"],
            "Issues": data["issues"],
            "sort_date": period_date,
        })

    if not chart_data:
        print("\nNo data available for chart (no complete months)")
        return

    # Sort by date for proper ordering
    chart_data.sort(key=lambda x: (x["sort_date"], x["Developer"]))

    # Create DataFrame
    import pandas as pd
    df = pd.DataFrame(chart_data)

    # Get date range for title
    min_date = min(d["sort_date"] for d in chart_data)
    max_date = max(d["sort_date"] for d in chart_data)
    # End date is last day of the max month
    import calendar
    last_day = calendar.monthrange(max_date.year, max_date.month)[1]
    end_date = max_date.replace(day=last_day)

    date_range = f"({min_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')})"

    import plotly.graph_objects as go

    developers = df["Developer"].unique().tolist()
    months = sorted(df["Month"].unique(), key=lambda m: datetime.strptime(m, "%b %Y"))

    # Color palette for months
    colors = px.colors.qualitative.Plotly

    # Build data lookup by month
    month_data = {}
    for i, month in enumerate(months):
        month_df = df[df["Month"] == month]
        dev_points = {row["Developer"]: row["Story Points"] for _, row in month_df.iterrows()}
        dev_issues = {row["Developer"]: row["Issues"] for _, row in month_df.iterrows()}
        month_data[month] = {
            "points": [dev_points.get(dev, 0) for dev in developers],
            "issues": [dev_issues.get(dev, 0) for dev in developers],
            "color": colors[i % len(colors)],
        }

    # Calculate trend lines for each developer
    # For grouped bars, positions are distributed around the developer index
    num_months = len(months)
    bar_width = 0.8 / num_months  # Total group width is ~0.8, divided among months

    def get_trend_line_data(dev_idx, value_key):
        """Calculate trend line for a developer, returning x and y coordinates."""
        # Get months where this developer has data (non-zero values)
        dev_months = []
        dev_values = []
        for month_idx, month in enumerate(months):
            value = month_data[month][value_key][dev_idx]
            if value > 0:
                dev_months.append(month_idx)
                dev_values.append(value)

        # Need at least 2 points for a trend line
        if len(dev_months) < 2:
            return None, None

        # Calculate x positions within the developer's bar group
        # Bars are centered around dev_idx, spread from -0.4 to +0.4
        group_width = 0.8
        x_positions = []
        for month_idx in dev_months:
            # Calculate offset for this month's bar within the group
            offset = (month_idx - (num_months - 1) / 2) * (group_width / num_months)
            x_positions.append(dev_idx + offset)

        # Fit linear regression
        x_arr = np.array(x_positions)
        y_arr = np.array(dev_values)
        coeffs = np.polyfit(range(len(x_arr)), y_arr, 1)  # Linear fit

        # Calculate y values for trend line at first and last x positions
        trend_y = np.polyval(coeffs, [0, len(x_arr) - 1])
        trend_x = [x_positions[0], x_positions[-1]]

        return trend_x, trend_y.tolist()

    # --- Chart 1: Story Points ---
    fig_sp = go.Figure()
    for month in months:
        fig_sp.add_trace(
            go.Bar(
                name=month,
                x=developers,
                y=month_data[month]["points"],
                text=month_data[month]["points"],
                textposition="outside",
                texttemplate="%{text:.0f}",
                marker_color=month_data[month]["color"],
            )
        )

    # Add trend lines for each developer (Story Points)
    for dev_idx, dev in enumerate(developers):
        trend_x, trend_y = get_trend_line_data(dev_idx, "points")
        if trend_x is not None:
            fig_sp.add_shape(
                type="line",
                x0=trend_x[0],
                y0=trend_y[0],
                x1=trend_x[1],
                y1=trend_y[1],
                line=dict(color="black", width=2),
                xref="x",
                yref="y",
            )

    fig_sp.update_layout(
        title=f"Story Points by Month {date_range}",
        xaxis_tickangle=-45,
        xaxis_title="Developer",
        yaxis_title="Story Points",
        font=dict(size=12),
        barmode="group",
        width=1200,
        height=600,
        legend_title_text="Month",
    )

    # Add vertical lines between developers
    for i in range(len(developers) - 1):
        fig_sp.add_vline(x=i + 0.5, line_width=1, line_dash="solid", line_color="lightgray")

    fig_sp.write_image("developer_story_points.png")
    print(f"\nChart saved to: developer_story_points.png")

    # --- Chart 2: Issues Resolved ---
    fig_issues = go.Figure()
    for month in months:
        fig_issues.add_trace(
            go.Bar(
                name=month,
                x=developers,
                y=month_data[month]["issues"],
                text=month_data[month]["issues"],
                textposition="outside",
                texttemplate="%{text:.0f}",
                marker_color=month_data[month]["color"],
            )
        )

    # Add trend lines for each developer (Issues)
    for dev_idx, dev in enumerate(developers):
        trend_x, trend_y = get_trend_line_data(dev_idx, "issues")
        if trend_x is not None:
            fig_issues.add_shape(
                type="line",
                x0=trend_x[0],
                y0=trend_y[0],
                x1=trend_x[1],
                y1=trend_y[1],
                line=dict(color="black", width=2),
                xref="x",
                yref="y",
            )

    fig_issues.update_layout(
        title=f"Issues Resolved by Month {date_range}",
        xaxis_tickangle=-45,
        xaxis_title="Developer",
        yaxis_title="Issues",
        font=dict(size=12),
        barmode="group",
        width=1200,
        height=600,
        legend_title_text="Month",
    )

    # Add vertical lines between developers
    for i in range(len(developers) - 1):
        fig_issues.add_vline(x=i + 0.5, line_width=1, line_dash="solid", line_color="lightgray")

    fig_issues.write_image("developer_issues.png")
    print(f"Chart saved to: developer_issues.png")

    print(f"\nDevelopers: {len(developers)}")
    print(f"Months: {', '.join(months)}")


def calculate_bitbucket_insights(bitbucket_client, jira_client, created_after):
    """
    Calculate developer insights from BitBucket commits.

    Args:
        bitbucket_client: BitBucketClient instance
        jira_client: JiraClient instance for issue type lookups
        created_after: Date string (YYYY-MM-DD) to filter commits
    """
    from collections import defaultdict
    from datetime import datetime
    import re

    # Reuse tester and valid developer lists from velocity feature
    testers = ["Allen Lai", "Henrik Schneider", "Michael Olstad", "Ryan Patz",
               "Dennis", "Ramyaa", "Pavithra", "Tannu", "Lundi", "Minal", "Prajwal"]

    valid_developers = [
        "Hemalatha Mallala",
        "Hemalatha Nallanna Gari",
        "NAGARAJ B S",
        "Roshini Jayalakshmi",
        "SNEHA HA",
        "Shashivardhan Manne",
    ]

    # Jira issue key pattern
    jira_pattern = re.compile(r'ASE-\d+')

    # Metrics aggregation
    developer_metrics = defaultdict(lambda: {
        "commits": 0,
        "lines_added": 0,
        "lines_deleted": 0,
        "files_touched": set(),
        "rework_commits": 0,
        "dark_commits": 0,
        "rework_breakdown": defaultdict(int),
        "repos": defaultdict(int),
    })

    # File history for rework detection: {file_path: [(author, date), ...]}
    file_history = defaultdict(list)

    # Cache for Jira issue types
    jira_issue_cache = {}

    # Statistics
    total_commits = 0
    matched_commits = 0
    unmatched_commits = 0

    print(f"\nFetching commits from {len(BITBUCKET_REPOS)} repositories...")

    for repo in BITBUCKET_REPOS:
        project = repo["project"]
        slug = repo["slug"]
        name = repo["name"]

        print(f"  Processing {name}...")
        commits = bitbucket_client.get_all_commits(project, slug, created_after)
        print(f"    Found {len(commits)} commits")

        # Add small delay between repos to avoid rate limiting
        time.sleep(0.5)

        for commit in commits:
            total_commits += 1

            # Match developer
            author = commit["author"]
            developer = match_developer(author, valid_developers, testers)

            if not developer:
                unmatched_commits += 1
                continue

            matched_commits += 1
            dev_normalized = normalize_name(developer)

            # Get diff stats
            diff_stats = bitbucket_client.get_commit_diff_stats(project, slug, commit["id"])

            # Check for Jira issue reference
            message = commit.get("message", "")
            jira_matches = jira_pattern.findall(message)
            jira_issue_type = None

            if jira_matches:
                issue_key = jira_matches[0]
                if issue_key not in jira_issue_cache:
                    try:
                        issue_details = jira_client.get_issue_details(issue_key)
                        if issue_details:
                            jira_issue_cache[issue_key] = issue_details.get("fields", {}).get("issuetype", {}).get("name")
                        else:
                            jira_issue_cache[issue_key] = None
                    except Exception:
                        jira_issue_cache[issue_key] = None
                jira_issue_type = jira_issue_cache.get(issue_key)
            else:
                developer_metrics[developer]["dark_commits"] += 1

            # Convert timestamp to datetime
            commit_date = datetime.fromtimestamp(commit["date"] / 1000)

            # Classify rework for each file
            is_rework = False
            rework_signals = {"file_churn": False, "same_author": False, "cross_author": False, "bug_fix": False}

            for file_path in diff_stats["files_changed"]:
                file_signals = classify_rework(
                    dev_normalized, commit_date, file_path, file_history, jira_issue_type
                )
                # Merge signals (OR logic)
                for signal, value in file_signals.items():
                    if value:
                        rework_signals[signal] = True
                        is_rework = True

                # Update file history
                file_history[file_path].append((dev_normalized, commit_date))

            # Aggregate metrics
            developer_metrics[developer]["commits"] += 1
            developer_metrics[developer]["lines_added"] += diff_stats["lines_added"]
            developer_metrics[developer]["lines_deleted"] += diff_stats["lines_deleted"]
            developer_metrics[developer]["files_touched"].update(diff_stats["files_changed"])
            developer_metrics[developer]["repos"][name] += 1

            if is_rework:
                developer_metrics[developer]["rework_commits"] += 1
                for signal, value in rework_signals.items():
                    if value:
                        developer_metrics[developer]["rework_breakdown"][signal] += 1

    # Print summary
    print(f"\nBitBucket Insights ({created_after} to today):")
    print(f"  Total commits analyzed: {total_commits}")
    print(f"  Matched to developers: {matched_commits}")
    print(f"  Unmatched (excluded): {unmatched_commits}")

    total_rework = sum(m["rework_commits"] for m in developer_metrics.values())
    total_dark = sum(m["dark_commits"] for m in developer_metrics.values())
    rework_pct = (total_rework / matched_commits * 100) if matched_commits > 0 else 0

    print(f"  Rework commits: {total_rework} ({rework_pct:.1f}%)")
    print(f"  Dark commits (no Jira ref): {total_dark}")

    # Generate charts (will be added in next task)
    generate_bitbucket_charts(developer_metrics, created_after)


def main():
    """Main program entry point"""
    parser = argparse.ArgumentParser(
        description="component Jira Data Center using REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -u https://jira.company.com -U username -P password
  %(prog)s -u https://jira.company.com -U username -P password --no-verify-ssl
  %(prog)s -u https://jira.company.com -U username -P password --max-results 100
        """,
    )

    parser.add_argument(
        "-u",
        "--url",
        required=True,
        help="Jira base URL (e.g., https://jira.company.com)",
    )

    parser.add_argument("-U", "--username", required=True, help="Jira username")

    parser.add_argument(
        "-P", "--password", required=True, help="Jira password or API token"
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=5000,
        help="Maximum number of results per component (default: 5000)",
    )

    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable SSL certificate verification",
    )

    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Only test connection, do not run queries",
    )

    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    parser.add_argument(
        "--story-points-summary",
        action="store_true",
        help="Display story points summary for all issues",
    )

    parser.add_argument(
        "--print-queries",
        action="store_true",
        help="Print the JQL queries being executed",
    )

    parser.add_argument(
        "--print-jira-issues",
        action="store_true",
        help="Print detailed Jira issues in JSON format",
    )

    parser.add_argument(
        "--generate-release-notes",
        action="store_true",
        help="Generate release notes table for all components",
    )

    parser.add_argument(
        "--include-commit-details",
        action="store_true",
        help="Include commit counts and resolution times in release notes (requires BitBucket API calls)",
    )

    parser.add_argument(
        "--developer-velocity",
        action="store_true",
        help="Calculate developer velocity (story points per month) for closed issues",
    )

    parser.add_argument(
        "--created-after",
        type=str,
        help="Filter issues created on or after this date (YYYY-MM-DD format, required for --developer-velocity)",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default="developer_velocity.csv",
        help="Output CSV file path (default: developer_velocity.csv)",
    )

    args = parser.parse_args()

    # Create Jira client
    print(f"Connecting to Jira at {args.url}...")
    client = JiraClient(
        args.url, args.username, args.password, verify_ssl=not args.no_verify_ssl
    )

    # Test connection
    server_info = client.test_connection()
    if not server_info:
        print(
            "Failed to connect to Jira. Please check your credentials and URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Connected to Jira Server")
    print(f"  Version: {server_info.get('version', 'Unknown')}")
    print(f"  Build: {server_info.get('buildNumber', 'Unknown')}")
    print(f"  Deployment Type: {server_info.get('deploymentType', 'Unknown')}")

    if args.test_only:
        print("\nConnection test successful!")
        sys.exit(0)

    # Generate release notes table if requested
    if args.generate_release_notes:
        print("\nGenerating release notes table...")
        bitbucket_client = BitBucketClient(
            args.username, args.password, verify_ssl=not args.no_verify_ssl
        )
        table = generate_release_notes_table(
            client,
            bitbucket_client,
            COMPONENTS,
            include_commit_details=args.include_commit_details,
        )
        print(table)
        sys.exit(0)

    # Calculate developer velocity if requested
    if args.developer_velocity:
        if not args.created_after:
            print(
                "Error: --created-after is required for --developer-velocity",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"\nCalculating developer velocity for issues created after {args.created_after}..."
        )
        calculate_developer_velocity(client, args.created_after, args.output_file)
        sys.exit(0)

    # Execute queries for backlog
    execute_component_queries(
        client=client,
        components=COMPONENTS,
        jql_prefix=COMMON_JQL_BACKLOG_PREFIX,
        query_description="BACKLOG",
        max_results=args.max_results,
        story_points_summary=args.story_points_summary,
        use_version=False,
        include_active_filter=False,
        print_queries=args.print_queries,
        print_jira_issues=args.print_jira_issues,
    )

    # Execute queries for active release
    execute_component_queries(
        client=client,
        components=COMPONENTS,
        jql_prefix=COMMON_JQL_ACTIVE_RELEASE_PREFIX,
        query_description="ACTIVE RELEASE",
        max_results=args.max_results,
        story_points_summary=args.story_points_summary,
        use_version=True,
        include_active_filter=True,
        print_queries=args.print_queries,
        print_jira_issues=args.print_jira_issues,
    )

    # Execute queries for total release
    execute_component_queries(
        client=client,
        components=COMPONENTS,
        jql_prefix=COMMON_JQL_TOTAL_RELEASE_PREFIX,
        query_description="TOTAL RELEASE",
        max_results=args.max_results,
        story_points_summary=args.story_points_summary,
        use_version=True,
        include_active_filter=False,
        print_queries=args.print_queries,
        print_jira_issues=args.print_jira_issues,
    )

    print(f"\n{'='*80}")
    print(f"Completed {len(COMPONENTS)*2} queries")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
