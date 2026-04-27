# ASE Project Management Tools

This repository contains Python tools for managing and visualizing Advanced Service Engineering (ASE) projects at Applied Materials.

## Overview

The toolkit consists of two main applications:

1. **status.py** - Project status visualization and reporting
2. **jira_info.py** - Jira Data Center REST API integration for issue tracking

---

## status.py

### Purpose
Generates visual reports for ASE projects including Gantt charts and bar charts to track project progress, backlog, and work remaining.

### Features
- **Gantt Chart Visualization**: Timeline view of active releases with percent complete color coding
- **Backlog Analysis**: Bar chart showing backlog hours by program
- **Work Remaining Analysis**: Bar chart displaying remaining hours for active releases by program

### Input Requirements
- Excel file: `Status.xlsx` containing the following columns:
  - `Program`: Project program name
  - `Active Release`: Current release identifier
  - `Active Release StartDate`: Release start date
  - `Active Release EndDate`: Release end date
  - `Active Release PercentComplete`: Completion percentage (0-1 scale)
  - `Features in Active Release`: Description of features
  - `Upcoming Items`: Future planned items
  - `Backlog`: Backlog hours (numeric)
  - `Active Release Remaining`: Remaining work hours (numeric)

### Output
Three PNG image files:
- `status_gantt_chart_image.png` - Timeline Gantt chart of all active releases
- `backlog_bar_chart_image.png` - Backlog hours by program
- `active_bar_chart_image.png` - Remaining work hours by program

### Dependencies
```python
pandas
plotly
kaleido  # Required for image export
openpyxl  # Required for Excel file reading
```

### Usage
```bash
python status.py
```

### Chart Configuration
- **Gantt Chart**: 1000x500 pixels, color-coded by completion (grey→green→blue)
- **Bar Charts**: 1000x500 pixels, color-coded by program
- **Date Range**: Automatically calculated from data with 3-11 month extensions

---

## jira_info.py

### Purpose
Command-line tool for querying Jira Data Center using REST API to retrieve and analyze ASE project issues, including story points and backlog tracking. Integrates with BitBucket Data Center for release notes validation and commit tracking.

### Features
- **Connection Testing**: Verify Jira server connectivity and retrieve server information
- **JQL Query Execution**: Execute predefined JQL queries for ASE project components
- **Story Points Analysis**: Extract and summarize story points by component
- **Backlog Tracking**: Query new issues with no fix version
- **Active Release Tracking**: Query in-progress issues for specific release versions
- **Release Notes Generation**: Parse BitBucket release notes and validate against Jira issue types
- **Commit Tracking**: Count commits per issue and calculate resolution times
- **Developer Velocity Charts**: Generate monthly story points and issues resolved charts per developer
- **Flexible Output**: Standard formatted output or JSON export

### Supported Components
The tool tracks components listed in the components.yaml file

### Query Types

The tool executes three types of queries for each component:

#### 1. Backlog Query
Retrieves new issues with no fix version assigned:
```jql
project = ASE and status = new and fixVersion is EMPTY and component = "<component>" ORDER BY Rank ASC
```

#### 2. Active Release Query
Retrieves in-progress issues for a specific release version:
```jql
project = ASE and status != CLOSED and component = "<component>" 
and status != Closed and status != DUPLICATE and status != REJECTED and status != VERIFICATION 
AND fixVersion = "<version>" ORDER BY Rank ASC
```

#### 3. Total Release Query
Retrieves all issues for a specific release version (including completed):
```jql
project = ASE and component = "<component>" AND fixVersion = "<version>" ORDER BY Rank ASC
```

### Command-Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `-u`, `--url` | Yes | Jira base URL (e.g., https://jira.company.com) |
| `-U`, `--username` | Yes | Jira username (used for both Jira and BitBucket) |
| `-P`, `--password` | Yes | Jira password or API token (used for both Jira and BitBucket) |
| `--max-results` | No | Maximum results per query (default: 5000) |
| `--no-verify-ssl` | No | Disable SSL certificate verification |
| `--test-only` | No | Only test connection, don't run queries |
| `--json` | No | Output results in JSON format |
| `--story-points-summary` | No | Display story points summary for all issues |
| `--print-queries` | No | Print the JQL queries being executed |
| `--print-jira-issues` | No | Print detailed Jira issues in JSON format |
| `--generate-release-notes` | No | Generate release notes table for all components |
| `--include-commit-details` | No | Include commit counts and resolution times (requires BitBucket API calls) |
| `--developer-velocity` | No | Generate developer velocity charts (story points and issues per month) |
| `--created-after` | No* | Filter issues created on or after this date (YYYY-MM-DD format, *required for --developer-velocity and --bitbucket-insights) |
| `--bitbucket-insights` | No | Calculate developer metrics from BitBucket commits and pull requests |
| `--include-commits` | No | Include commit analysis in --bitbucket-insights (slower, fetches commit diffs) |

### Usage Examples

**Test Connection:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --test-only
```

**Query Issues with Story Points Summary:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --story-points-summary
```

**Query with More Results:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --max-results 100
```

**Query with SSL Verification Disabled:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --no-verify-ssl
```

**Generate Release Notes Table:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --generate-release-notes
```

**Generate Release Notes with Commit Details:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --generate-release-notes --include-commit-details
```

**Print JQL Queries:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --print-queries
```

**Generate Developer Velocity Charts:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --developer-velocity --created-after 2026-01-01
```

**Generate BitBucket Insights (Pull Requests):**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --bitbucket-insights --created-after 2026-01-01
```

**Generate BitBucket Insights with Commit Analysis:**
```bash
python jira_info.py -u https://jira.company.com -U username -P password --bitbucket-insights --include-commits --created-after 2026-01-01
```

### Output Features

#### Standard Output
- Issue key, summary, status, priority, and assignee
- Formatted hierarchical display

#### Story Points Summary
When using `--story-points-summary`:
- Executes all three query types (BACKLOG, ACTIVE RELEASE, TOTAL RELEASE)
- Individual issue breakdown with story points and components (optional detail view)
- Story points grouped by component for each query type
- Separate summaries for:
  - **Backlog**: All new unscheduled work
  - **Active Release**: Current in-progress work
  - **Total Release**: All work in the release (completed + in-progress)
- Summary statistics for each query type:
  - Total issues
  - Issues with story points assigned
  - Total story points
  - Average story points per issue

#### Release Notes Table Generation
When using `--generate-release-notes`:
- Fetches release notes from BitBucket repositories for each component
- Parses release notes to extract release tags and categorized issues (Enhancements vs Defects)
- Validates that release notes categorization matches actual Jira issue types
- Logs warnings for any mismatches between release notes and Jira
- Optionally includes (with `--include-commit-details`):
  - Total commit counts from BitBucket for each issue
  - Average time to resolve issues (from creation to resolution)
  - Developer names who contributed to the release
- Outputs CSV format with columns: Component, Version, Release Tag, Enhancements, Defects, Total Commits, Time to Resolve (days)

#### Developer Velocity Charts
When using `--developer-velocity --created-after YYYY-MM-DD`:
- Queries all closed ASE issues created after the specified date
- Tracks story points completed per developer per month
- Generates two PNG chart files:
  - `developer_story_points.png` - Story points by month per developer
  - `developer_issues.png` - Issues resolved by month per developer
- **Tester Exclusion**: Automatically excludes testers from velocity metrics. If an issue is assigned to a tester at "In Progress" time, the tool searches the assignee history to credit the last valid developer who worked on it.
- **Visual Features**:
  - Grouped bar charts by month with color coding
  - Vertical separator lines between developers
  - Data labels showing exact values

#### BitBucket Insights
When using `--bitbucket-insights --created-after YYYY-MM-DD`:
- Analyzes pull requests across all configured BitBucket repositories
- Tracks merged PRs per developer per month
- Generates chart files:
  - `total_pull_requests.png` - Total PRs by month with optional staffing overlay
  - `developer_pull_requests.png` - PRs by month per developer
- With `--include-commits` (slower, more detailed):
  - `developer_commits.png` - Commits by month per developer
  - `developer_rework.png` - Rework commits by month per developer
  - `developer_repo_dist.png` - Repository distribution by developer
- **Staffing Overlay**: If `AMAT Developer Project Duration.xlsx` exists, displays headcount trend on the total PRs chart

### Dependencies
```python
requests
pyyaml
```

### Architecture
- **JiraClient Class**: Handles Jira Data Center REST API authentication and requests
  - Session management with persistent connection
  - Methods for testing connection, searching issues, and getting issue details
- **BitBucketClient Class**: Handles BitBucket Data Center REST API interactions
  - Fetches file content from repositories (release notes)
  - Retrieves commits linked to Jira issues
  - Implements exponential backoff retry logic for rate limiting (429 errors)
- **ReleaseNotesParser Class**: Parses release notes text files
  - Extracts release tags (e.g., `#Tag 26.01.01`)
  - Categorizes Jira issues as Enhancements or Defects based on section headers
- **execute_component_queries Function**: Centralized query execution engine that:
  - Builds JQL queries dynamically based on query type
  - Handles component iteration and version filtering
  - Processes and aggregates results across all components
  - Eliminates code duplication across different query types
- **generate_release_notes_table Function**: Orchestrates release notes processing
  - Fetches release notes from BitBucket
  - Validates issue categorization against Jira
  - Optionally calculates commit counts and resolution times
- **Error Handling**: Comprehensive error reporting for connection and query failures
- **SSL Support**: Configurable SSL verification with warning suppression

### Code Organization
The tool uses a modular design with:
- **Query Configuration**: Centralized JQL prefixes and filters as constants
- **Component Configuration**: `components.yaml` file defines component metadata and BitBucket release notes URLs
- **Team Configuration**: `team.yaml` file defines valid developers and testers for attribution
- **Reusable Functions**: Single `execute_component_queries()` function handles all three query types (BACKLOG, ACTIVE RELEASE, TOTAL RELEASE)
- **Data Extraction**: Separate functions for story points extraction and summary generation
- **Release Processing**: Dedicated functions for parsing release notes and validating against Jira
- **Output Formatting**: Consistent formatting functions for both detailed and summary views

### Custom Fields
- `customfield_10106`: Story Points field in Jira

---

## Installation

### Install Required Dependencies
```bash
pip install pandas plotly kaleido openpyxl requests pyyaml
```

### File Structure
```
schedule/
├── README.md
├── CLAUDE.md                       # Claude Code instructions
├── status.py
├── jira_info.py
├── staffing.py                     # Staffing data module
├── components.yaml                 # Component and BitBucket repo configuration
├── team.yaml                       # Developer and tester lists
├── Status.xlsx                     # Input file for status.py
├── status_gantt_chart_image.png    # Output from status.py
├── backlog_bar_chart_image.png     # Output from status.py
├── active_bar_chart_image.png      # Output from status.py
├── developer_story_points.png      # Output from --developer-velocity
├── developer_issues.png            # Output from --developer-velocity
├── developer_velocity.png          # Output from --developer-velocity
├── total_pull_requests.png         # Output from --bitbucket-insights
├── developer_pull_requests.png     # Output from --bitbucket-insights
├── developer_commits.png           # Output from --bitbucket-insights --include-commits
├── developer_rework.png            # Output from --bitbucket-insights --include-commits
└── developer_repo_dist.png         # Output from --bitbucket-insights --include-commits
```

---

## Workflow Integration

### Typical Workflow
1. **Query Jira**: Use `jira_info.py` to extract current project data across all three query types
   - Backlog items for planning future work
   - Active release progress for current sprint tracking
   - Total release metrics for overall project assessment
2. **Update Excel**: Populate `Status.xlsx` with latest project information
3. **Generate Reports**: Run `status.py` to create visual reports
4. **Review**: Analyze charts for project status and resource allocation

### Automation Considerations
- `jira_info.py` can be integrated into CI/CD pipelines
- Output can be redirected to files for logging
- Story points data can be exported as JSON for further processing
- Image outputs from `status.py` can be embedded in reports or dashboards
- The modular query execution allows easy addition of new query types

---

## Security Notes

- **Credentials**: Never commit passwords or API tokens to version control
- **SSL Verification**: Use `--no-verify-ssl` only in trusted environments
- **API Tokens**: Prefer API tokens over passwords for authentication
- **Environment Variables**: Consider using environment variables for credentials

---

## Troubleshooting

### status.py Issues
- **Missing Excel File**: Ensure `Status.xlsx` exists in the same directory
- **Date Format Errors**: Verify date columns are properly formatted in Excel
- **Image Export Fails**: Install `kaleido` package for Plotly image export

### jira_info.py Issues
- **Connection Failed**: Verify URL, username, and password
- **SSL Certificate Error**: Use `--no-verify-ssl` or install proper certificates
- **No Results**: Check JQL syntax and project permissions
- **Story Points Not Showing**: Verify custom field ID matches your Jira instance
- **Rate Limiting (429 errors)**: Tool automatically retries with exponential backoff (2, 4, 8 seconds)
- **Release Notes Parsing**: Ensure release notes follow expected format with `#Tag` headers
- **BitBucket Access**: Ensure credentials have access to BitBucket repositories

---

## Contributing

When modifying queries in `jira_info.py`:
1. Update `components.yaml` with new components, including:
   - `component`: Jira component name
   - `name`: Display name
   - `version`: Current fix version (or null)
   - `release_notes`: BitBucket URL to ReleaseNotes.txt (or null)
2. Update `team.yaml` to add/remove developers or testers
3. Ensure version numbers match Jira fix versions
4. Test queries using `--test-only` before full execution
5. Use the `execute_component_queries()` function for new query types to maintain consistency
6. Add new JQL prefix constants if needed for additional query patterns

When updating visualizations in `status.py`:
1. Maintain consistent chart dimensions for reporting
2. Update color schemes in the configuration section
3. Test with actual data before deployment

---

## License

Internal use only - Applied Materials ASE Team

---

## Contact

For questions or issues, contact the ASE Project Management team.
