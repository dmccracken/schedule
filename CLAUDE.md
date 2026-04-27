# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ASE (Advanced Service Engineering) Project Management Tools for Applied Materials. This toolkit integrates Jira Data Center REST API and BitBucket for project tracking, visualization, and release management.

## Core Applications

### status.py - Project Status Visualization
Generates visual reports from Excel data (`Status.xlsx`):
- Gantt charts showing active releases with completion percentages
- Bar charts for backlog and remaining work by program

**Run:** `python status.py`

**Input:** `Status.xlsx` with columns: Program, Active Release, Active Release StartDate/EndDate, Active Release PercentComplete, Features in Active Release, Upcoming Items, Backlog, Active Release Remaining

**Output:** Three PNG files - `status_gantt_chart_image.png`, `backlog_bar_chart_image.png`, `active_bar_chart_image.png`

### jira_info.py - Jira/BitBucket Integration
Command-line tool for querying Jira issues and generating release reports.

**Test connection:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --test-only
```

**Query with story points:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --story-points-summary
```

**Generate release notes table:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --generate-release-notes
```

**With commit details:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --generate-release-notes --include-commit-details
```

## Architecture

### jira_info.py Structure

**JiraClient class** (lines 150-249):
- Handles Jira Data Center REST API authentication via HTTPBasicAuth
- Session-based connection management with SSL configuration
- Core methods:
  - `test_connection()`: Validates credentials and returns server info
  - `search_issues(jql, max_results, fields)`: Executes JQL queries
  - `get_issue_details(issue_key)`: Fetches full issue data including created/resolved dates

**BitBucketClient class** (lines 20-148):
- Manages BitBucket Data Center REST API interactions
- Implements exponential backoff retry logic for 429 rate limiting
- Core methods:
  - `get_file_content(url)`: Fetches raw file content (converts browse URLs to raw)
  - `get_commits_for_issue(project_key, repo_slug, issue_key)`: Extracts commits linked to Jira issue

**Query Execution Engine**:
- `execute_component_queries()` (lines 757-828): Centralized query executor that handles all three query types (BACKLOG, ACTIVE RELEASE, TOTAL RELEASE)
- Eliminates code duplication by dynamically building JQL queries based on parameters
- Supports optional version filtering and status filtering

**Release Notes Processing**:
- `ReleaseNotesParser` class (lines 669-754): Parses release notes text files to extract:
  - Release tags (e.g., `#Tag 26.01.01`)
  - Categorized Jira issues (Enhancements vs Defects)
- `generate_release_notes_table()` (lines 338-504):
  - Fetches release notes from BitBucket
  - Cross-references Jira issue types against release notes categorization
  - Validates that release notes match actual Jira issue types (logs warnings on mismatch)
  - Optionally calculates commit counts and resolution times

### Data Flow

**Typical Workflow:**
1. Query Jira with `jira_info.py` to extract project data (backlog, active releases, totals)
2. Update `Status.xlsx` with latest information
3. Generate visual reports with `status.py`

**Release Notes Workflow:**
1. Tool fetches release notes from BitBucket repositories
2. Parses notes to identify release tags and associated Jira issues
3. Queries Jira API for actual issue types (Defect vs Enhancement)
4. Validates that release notes categorization matches Jira issue types
5. Optionally fetches commit data from BitBucket for each issue
6. Generates CSV with metrics: Component, Version, Release Tag, Enhancements, Defects, Total Commits, Time to Resolve (days)

## Components Tracked

The `COMPONENTS` list in `components.yaml` defines all tracked ASE components:
- Alarms Dashboard (Alarm_26.01)
- AutoUVA Dashboard (AUTO_UVA_V4.0)
- CSV Dashboard (CSV_26.01)
- DES Dashboard (DES_V2)
- Everest Dashboard (Everest_V2)
- PPTS Dashboard (PPTS_V11)
- ToolConnection Dashboard (Toolconnection2.0)
- Guardband, EPD, and PdM Dashboards

Each component includes:
- `component`: Jira component name
- `name`: Display name
- `version`: Current fix version (or None if not versioned)
- `release_notes`: BitBucket URL to ReleaseNotes.txt file (or None)

## JQL Query Types

Three query patterns for each component:

1. **Backlog** (line 659): `project = ASE and status = new and fixVersion is EMPTY and component = "<component>"`
2. **Active Release** (lines 662-665): `project = ASE and status != CLOSED and component = "<component>" and status != Closed and status != DUPLICATE and status != REJECTED and status != VERIFICATION AND fixVersion = "<version>"`
3. **Total Release** (line 663): `project = ASE and component = "<component>" AND fixVersion = "<version>"`

## Custom Fields

- `customfield_10106`: Story Points field in Jira (referenced in line 280)

## Dependencies

Install all required packages:
```bash
pip install pandas plotly kaleido openpyxl requests pyyaml
```

- **pandas, openpyxl**: Excel file reading and data manipulation
- **plotly, kaleido**: Chart generation and PNG export
- **requests**: REST API interactions with Jira and BitBucket
- **pyyaml**: YAML configuration file loading

## Important Implementation Notes

**When modifying queries:**
- Add new components to the `COMPONENTS` list with proper structure
- Use `execute_component_queries()` for consistency across query types
- New query patterns should be added as JQL prefix constants (lines 659-666)

**When modifying visualization:**
- Chart dimensions are standardized at 1000x500 pixels
- Color schemes: Gantt charts use grey→green→blue gradient based on completion percentage
- Date ranges auto-calculate with 3-11 month extensions for visibility

**SSL and Authentication:**
- Use `--no-verify-ssl` only in trusted environments
- BitBucket and Jira use HTTP Basic Authentication with session management
- Rate limiting handled with exponential backoff (2, 4, 8 second waits)

**Release Notes Parsing:**
- Expects specific format with `#Tag` or `# Tag` headers followed by version numbers
- Categorizes issues based on section headers containing "enhancement" or "bug/fix/defect" keywords
- Defaults uncategorized issues to defects
- Validates Jira issue types (Defect vs non-Defect) against release notes categories

## File Locations

- Input Excel: `Status.xlsx` (current directory)
- Output images: `status_gantt_chart_image.png`, `backlog_bar_chart_image.png`, `active_bar_chart_image.png`
- Release notes CSV: Output goes to stdout (redirect to file if needed)
