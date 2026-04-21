# BitBucket Developer Insights Design

**Date:** 2026-04-21  
**Status:** Approved  
**Author:** Claude + User collaboration

## Overview

Add BitBucket commit analysis to `jira_info.py` via a new `--bitbucket-insights` flag. This feature tracks developer productivity metrics from commit history including commit counts, lines of code changed, and rework patterns.

## Requirements

### Functional Requirements

1. New CLI flag `--bitbucket-insights` that can run standalone or combined with `--developer-velocity`
2. Reuse existing `--created-after` parameter for date filtering
3. Track metrics across 6 hardcoded repositories in the FSSRPT project
4. Generate charts organized by developer (similar to existing velocity charts)
5. Apply same tester exclusion logic as developer velocity feature

### Metrics to Track

| Metric | Description |
|--------|-------------|
| Commits | Total commit count per developer |
| Lines Added | Total lines of code added |
| Lines Deleted | Total lines of code deleted |
| Files Touched | Unique files modified |
| Rework Commits | Commits flagged as rework (any signal) |
| Dark Commits | Commits without Jira issue reference |

### Rework Detection

Four signals combined with OR logic:

| Signal | Detection Method |
|--------|------------------|
| File Churn | Same file modified 3+ times within 30 days by any author |
| Bug-Fix Commits | Commit references a Jira issue with type = "Defect" |
| Same-Author Rework | Developer modifies a file they committed to within 30 days |
| Cross-Author Rework | Developer modifies a file another developer committed to within 30 days |

## Architecture

### Repository Configuration

Hardcoded list similar to existing COMPONENTS:

```python
BITBUCKET_REPOS = [
    {"project": "FSSRPT", "slug": "des", "name": "DES"},
    {"project": "FSSRPT", "slug": "csv", "name": "CSV"},
    {"project": "FSSRPT", "slug": "trace_segmentation", "name": "Trace Segmentation"},
    {"project": "FSSRPT", "slug": "alarm_dispatch", "name": "Alarm Dispatch"},
    {"project": "FSSRPT", "slug": "tool_connection_control_app", "name": "Tool Connection"},
    {"project": "FSSRPT", "slug": "pts_dashboard", "name": "PTS Dashboard"},
]
```

### New BitBucketClient Methods

1. **`get_all_commits(project, repo, since_date)`**
   - Fetch all commits in date range with pagination
   - Returns list of commit objects with author, date, message, files

2. **`get_commit_diff_stats(project, repo, commit_id)`**
   - Fetch diff statistics for a single commit
   - Returns lines added, lines deleted, files changed

### Data Flow

```
1. For each repo in BITBUCKET_REPOS:
   +-- Fetch all commits since --created-after
   +-- For each commit:
   |   +-- Extract author, date, message, files changed
   |   +-- Get diff stats (lines added/deleted)
   |   +-- Check for Jira issue key in message (e.g., ASE-1234)
   |   +-- Flag rework signals
   +-- Aggregate by developer (fuzzy name matching)

2. Cross-reference with Jira:
   +-- For commits with issue keys, fetch issue type
   +-- Mark as rework if issue type = "Defect"

3. Generate charts by developer
```

### Developer Matching

Fuzzy name matching between BitBucket authors and valid_developers list:

```python
def normalize_name(name):
    """Normalize for comparison: lowercase, remove suffixes, strip whitespace"""
    name = name.lower().strip()
    name = name.replace(" --cntr", "")
    return name

def match_developer(bitbucket_author, valid_developers):
    """Find matching developer from valid_developers list"""
    normalized = normalize_name(bitbucket_author)
    
    for dev in valid_developers:
        if normalize_name(dev) == normalized:
            return dev
        # Partial match: "Hemalatha M" matches "Hemalatha Mallala"
        if normalized in normalize_name(dev) or normalize_name(dev) in normalized:
            return dev
    
    return None  # No match = excluded from output
```

### Filtering

- Reuse existing `testers` list - commits from testers excluded
- Reuse existing `valid_developers` list - only these developers appear in charts
- Unmatched authors logged for debugging but excluded from charts

### Rework Classification

```python
def classify_rework(commit, file_path, file_history, jira_issue_type):
    """
    Classify a commit's rework signals for a specific file.
    
    Args:
        commit: Commit object with author, date
        file_path: Path of file being analyzed
        file_history: Dict mapping file_path to list of (author, date, commit_id)
        jira_issue_type: Issue type from Jira if commit references an issue, else None
    
    Returns:
        Dict of rework signals (all boolean)
    """
    recent_commits = [c for c in file_history[file_path] 
                      if (commit.date - c.date).days <= 30]
    
    return {
        "file_churn": len(recent_commits) >= 2,  # This would be 3rd+ touch
        "same_author": any(c.author == commit.author for c in recent_commits),
        "cross_author": any(c.author != commit.author for c in recent_commits),
        "bug_fix": jira_issue_type == "Defect",
    }
```

## Output

### Charts

| File | Description |
|------|-------------|
| `developer_commits.png` | Grouped bar chart: commits, lines added, lines deleted by developer with monthly breakdown and trend lines |
| `developer_rework.png` | Stacked bar chart: rework breakdown by signal type (file churn, bug-fix, same-author, cross-author) |
| `developer_repo_dist.png` | Stacked bar chart: commits per repository showing where each developer focuses |

### Console Summary

```
BitBucket Insights (2025-01-01 to 2026-04-21):
  Total commits analyzed: 847
  Matched to developers: 792
  Unmatched (excluded): 55
  Rework commits: 156 (19.7%)
  Dark commits (no Jira ref): 89
```

## CLI Interface

```
--bitbucket-insights    Calculate developer metrics from BitBucket commits
--created-after DATE    Filter commits on or after this date (YYYY-MM-DD format, 
                        required for --bitbucket-insights)
```

**Example usage:**

```bash
# BitBucket insights only
python jira_info.py -u URL -U user -P pass --bitbucket-insights --created-after 2025-01-01

# Combined with developer velocity
python jira_info.py -u URL -U user -P pass --developer-velocity --bitbucket-insights --created-after 2025-01-01
```

## Rate Limiting

- Reuse existing exponential backoff pattern (2, 4, 8 second waits on 429)
- Add small delay (0.5s) between repository fetches to avoid bursts
- Log rate limit events to stderr

## Error Handling

- Continue processing if individual commit diff fetch fails (log warning)
- Continue processing if individual Jira issue fetch fails (mark as unknown type)
- Fail gracefully if entire repository is inaccessible (log error, continue with others)

## Testing

1. Test with small date range to verify data flow
2. Verify developer name matching with known authors
3. Verify rework detection with known bug-fix commits
4. Verify chart generation matches expected format

## Future Considerations (Out of Scope)

- CLI-configurable repository list
- Configurable rework window (currently hardcoded at 30 days)
- PR/code review metrics
- Commit frequency/time patterns
