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

            return {
                "key": issue_key,
                "created": created,
                "resolved": resolutiondate,
                "assignee": assignee.get("displayName") if assignee else None,
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issue {issue_key}: {e}", file=sys.stderr)
            return None


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


def generate_release_notes_table(jira_client, bitbucket_client, components):
    """
    Generate release notes table for all components

    Args:
        jira_client: JiraClient instance
        bitbucket_client: BitBucketClient instance
        components: List of component dictionaries

    Returns:
        Markdown formatted table as string
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

            # Process each issue
            for issue_key in all_issues:
                # Get issue details from Jira
                issue_details = jira_client.get_issue_details(issue_key)
                if issue_details:
                    # Calculate resolution time
                    res_time = calculate_resolution_time(
                        issue_details.get("created"), issue_details.get("resolved")
                    )
                    if res_time is not None:
                        resolution_times.append(res_time)

                # Get commits from BitBucket
                commits = bitbucket_client.get_commits_for_issue(
                    project_key, repo_slug, issue_key
                )
                total_commits += len(commits)

                # Track developers
                for commit in commits:
                    developers.add(commit.get("author", "Unknown"))

            # Calculate average resolution time
            avg_resolution = (
                sum(resolution_times) / len(resolution_times) if resolution_times else 0
            )

            # Add to table data
            table_data.append(
                {
                    "component": component_name,
                    "version": version,
                    "release_tag": release_tag,
                    "enhancements": len(enhancements),
                    "defects": len(defects),
                    "commits": total_commits,
                    "avg_resolution_days": avg_resolution,
                    "developers": (
                        ", ".join(sorted(developers)) if developers else "N/A"
                    ),
                }
            )

    # Generate markdown table
    if not table_data:
        return "No release notes data found."

    markdown = "\n## Release Notes Summary\n\n"
    markdown += "| Component | Version | Release Tag | Enhancements | Defects | Commits | Avg Resolution (days) |\n"
    markdown += "|-----------|---------|-------------|--------------|---------|---------|----------------------|\n"

    for row in table_data:
        markdown += f"| {row['component']} | {row['version']} | {row['release_tag']} | "
        markdown += f"{row['enhancements']} | {row['defects']} | {row['commits']} | "
        markdown += f"{row['avg_resolution_days']:.1f} |\n"

    return markdown


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
        "version": "AUTO_UVA_V4.0",
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
        "version": "DES_V2",
        "release_notes": None,
    },
    {
        "component": "Everest",
        "name": "Everest Dashboard",
        "version": "Everest_V2",
        "release_notes": None,
    },
    {
        "component": "PPTS",
        "name": "PPTS Dashboard",
        "version": "PPTS_V11",
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
        table = generate_release_notes_table(client, bitbucket_client, COMPONENTS)
        print(table)
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
