# BitBucket Developer Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--bitbucket-insights` flag to jira_info.py that analyzes developer commit activity, lines changed, and rework patterns across 6 BitBucket repositories.

**Architecture:** Extend BitBucketClient with methods to fetch all commits and diff stats. Add a new `calculate_bitbucket_insights()` function that aggregates metrics by developer and generates three charts (commits, rework, repo distribution). Reuse existing tester exclusion logic and name matching.

**Tech Stack:** Python, requests, plotly, pandas, BitBucket Data Center REST API

---

## File Structure

All changes are in a single file:
- **Modify:** `jira_info.py`
  - Add `BITBUCKET_REPOS` constant (after `COMPONENTS`)
  - Add 2 new methods to `BitBucketClient` class
  - Add helper functions: `normalize_name()`, `match_developer()`, `classify_rework()`
  - Add main function: `calculate_bitbucket_insights()`
  - Update CLI argument parsing in `main()`

**Output files generated:**
- `developer_commits.png`
- `developer_rework.png`
- `developer_repo_dist.png`

---

### Task 1: Add BITBUCKET_REPOS Configuration

**Files:**
- Modify: `jira_info.py` (after COMPONENTS list, around line 895)

- [ ] **Step 1: Add BITBUCKET_REPOS constant**

Add after the `COMPONENTS` list (around line 895):

```python
# BitBucket repositories for developer insights
BITBUCKET_REPOS = [
    {"project": "FSSRPT", "slug": "des", "name": "DES"},
    {"project": "FSSRPT", "slug": "csv", "name": "CSV"},
    {"project": "FSSRPT", "slug": "trace_segmentation", "name": "Trace Segmentation"},
    {"project": "FSSRPT", "slug": "alarm_dispatch", "name": "Alarm Dispatch"},
    {"project": "FSSRPT", "slug": "tool_connection_control_app", "name": "Tool Connection"},
    {"project": "FSSRPT", "slug": "pts_dashboard", "name": "PTS Dashboard"},
]
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add BITBUCKET_REPOS configuration for developer insights"
```

---

### Task 2: Add BitBucketClient.get_all_commits() Method

**Files:**
- Modify: `jira_info.py:79` (add new method to BitBucketClient class, before `get_commits_for_issue`)

- [ ] **Step 1: Add get_all_commits method**

Add inside `BitBucketClient` class (after `get_file_content`, before `get_commits_for_issue`):

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add BitBucketClient.get_all_commits() method"
```

---

### Task 3: Add BitBucketClient.get_commit_diff_stats() Method

**Files:**
- Modify: `jira_info.py` (add new method to BitBucketClient class, after `get_all_commits`)

- [ ] **Step 1: Add get_commit_diff_stats method**

Add inside `BitBucketClient` class (after `get_all_commits`):

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add BitBucketClient.get_commit_diff_stats() method"
```

---

### Task 4: Add Developer Name Matching Functions

**Files:**
- Modify: `jira_info.py` (add after `get_velocity_period` function, around line 560)

- [ ] **Step 1: Add normalize_name function**

Add after `get_velocity_period` function:

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add developer name matching functions"
```

---

### Task 5: Add Rework Classification Function

**Files:**
- Modify: `jira_info.py` (add after `match_developer` function)

- [ ] **Step 1: Add classify_rework function**

Add after `match_developer`:

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add rework classification function"
```

---

### Task 6: Add Main calculate_bitbucket_insights Function (Data Collection)

**Files:**
- Modify: `jira_info.py` (add after `calculate_developer_velocity` function)

- [ ] **Step 1: Add calculate_bitbucket_insights function (Part 1: Data collection)**

Add after `calculate_developer_velocity`:

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add calculate_bitbucket_insights function for data collection"
```

---

### Task 7: Add Chart Generation Function

**Files:**
- Modify: `jira_info.py` (add after `calculate_bitbucket_insights`)

- [ ] **Step 1: Add generate_bitbucket_charts function**

Add after `calculate_bitbucket_insights`:

```python
def generate_bitbucket_charts(developer_metrics, created_after):
    """
    Generate charts from BitBucket developer metrics.
    
    Args:
        developer_metrics: Dict of developer -> metrics
        created_after: Start date string for chart title
    """
    import plotly.graph_objects as go
    from datetime import datetime
    
    if not developer_metrics:
        print("\nNo data available for charts")
        return
    
    # Prepare data
    developers = sorted(developer_metrics.keys())
    
    # Clean up names for display
    display_names = [d.replace(" --CNTR", "") for d in developers]
    
    # Chart 1: Commits & Lines Changed
    commits = [developer_metrics[d]["commits"] for d in developers]
    lines_added = [developer_metrics[d]["lines_added"] for d in developers]
    lines_deleted = [developer_metrics[d]["lines_deleted"] for d in developers]
    
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name="Commits", x=display_names, y=commits, marker_color="#636EFA"))
    fig1.add_trace(go.Bar(name="Lines Added", x=display_names, y=lines_added, marker_color="#00CC96"))
    fig1.add_trace(go.Bar(name="Lines Deleted", x=display_names, y=lines_deleted, marker_color="#EF553B"))
    
    fig1.update_layout(
        title=f"Developer Commits & Lines Changed (since {created_after})",
        xaxis_title="Developer",
        yaxis_title="Count",
        barmode="group",
        width=1200,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig1.write_image("developer_commits.png")
    print("\nGenerated: developer_commits.png")
    
    # Chart 2: Rework Analysis
    rework_file_churn = [developer_metrics[d]["rework_breakdown"]["file_churn"] for d in developers]
    rework_bug_fix = [developer_metrics[d]["rework_breakdown"]["bug_fix"] for d in developers]
    rework_same_author = [developer_metrics[d]["rework_breakdown"]["same_author"] for d in developers]
    rework_cross_author = [developer_metrics[d]["rework_breakdown"]["cross_author"] for d in developers]
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="File Churn", x=display_names, y=rework_file_churn, marker_color="#636EFA"))
    fig2.add_trace(go.Bar(name="Bug Fix", x=display_names, y=rework_bug_fix, marker_color="#EF553B"))
    fig2.add_trace(go.Bar(name="Same-Author Rework", x=display_names, y=rework_same_author, marker_color="#FFA15A"))
    fig2.add_trace(go.Bar(name="Cross-Author Rework", x=display_names, y=rework_cross_author, marker_color="#AB63FA"))
    
    fig2.update_layout(
        title=f"Developer Rework Analysis (since {created_after})",
        xaxis_title="Developer",
        yaxis_title="Commits with Rework Signal",
        barmode="stack",
        width=1200,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig2.write_image("developer_rework.png")
    print("Generated: developer_rework.png")
    
    # Chart 3: Repository Distribution
    repo_names = sorted(set(
        repo for d in developers for repo in developer_metrics[d]["repos"].keys()
    ))
    
    fig3 = go.Figure()
    for repo in repo_names:
        repo_commits = [developer_metrics[d]["repos"].get(repo, 0) for d in developers]
        fig3.add_trace(go.Bar(name=repo, x=display_names, y=repo_commits))
    
    fig3.update_layout(
        title=f"Developer Repository Distribution (since {created_after})",
        xaxis_title="Developer",
        yaxis_title="Commits",
        barmode="stack",
        width=1200,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig3.write_image("developer_repo_dist.png")
    print("Generated: developer_repo_dist.png")
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 3: Commit**

```bash
git add jira_info.py
git commit -m "feat: add generate_bitbucket_charts function"
```

---

### Task 8: Add CLI Argument and Main Integration

**Files:**
- Modify: `jira_info.py:1536` (add new argument after --developer-velocity)
- Modify: `jira_info.py:1596` (add handler after developer_velocity block)

- [ ] **Step 1: Add --bitbucket-insights CLI argument**

Add after the `--output-file` argument (around line 1553):

```python
    parser.add_argument(
        "--bitbucket-insights",
        action="store_true",
        help="Calculate developer metrics from BitBucket commits (requires --created-after)",
    )
```

- [ ] **Step 2: Add handler in main() for bitbucket-insights**

Add after the developer_velocity block (after the `calculate_developer_velocity` call):

```python
    # Calculate BitBucket insights if requested
    if args.bitbucket_insights:
        if not args.created_after:
            print(
                "Error: --created-after is required for --bitbucket-insights",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"\nCalculating BitBucket insights for commits after {args.created_after}..."
        )
        bitbucket_client = BitBucketClient(
            args.username, args.password, verify_ssl=not args.no_verify_ssl
        )
        calculate_bitbucket_insights(bitbucket_client, client, args.created_after)
        
        # Exit if only bitbucket-insights was requested (not combined with other queries)
        if not args.story_points_summary and not args.developer_velocity:
            sys.exit(0)
```

- [ ] **Step 3: Verify syntax**

Run: `python -m py_compile jira_info.py`
Expected: No output (successful compilation)

- [ ] **Step 4: Commit**

```bash
git add jira_info.py
git commit -m "feat: add --bitbucket-insights CLI argument and handler"
```

---

### Task 9: Integration Testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Test help output**

Run: `python jira_info.py --help`
Expected: Should show `--bitbucket-insights` in the help text

- [ ] **Step 2: Test missing --created-after validation**

Run: `python jira_info.py -u https://jira.amat.com -U testuser -P testpass --bitbucket-insights`
Expected: Error message "Error: --created-after is required for --bitbucket-insights"

- [ ] **Step 3: Test with small date range (requires valid credentials)**

Run: `python jira_info.py -u <JIRA_URL> -U <username> -P <password> --bitbucket-insights --created-after 2026-04-01 --no-verify-ssl`

Expected output:
- Console shows "Fetching commits from 6 repositories..."
- Console shows processing messages for each repo
- Console shows summary statistics
- Three PNG files generated: `developer_commits.png`, `developer_rework.png`, `developer_repo_dist.png`

- [ ] **Step 4: Verify charts are valid images**

Open each generated PNG file and verify:
- `developer_commits.png`: Grouped bar chart with commits, lines added, lines deleted
- `developer_rework.png`: Stacked bar chart with rework breakdown
- `developer_repo_dist.png`: Stacked bar chart with repo distribution

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete BitBucket developer insights feature

Adds --bitbucket-insights flag that analyzes:
- Commit counts per developer
- Lines of code added/deleted
- Rework detection (file churn, bug-fix, same/cross-author)
- Repository distribution

Generates three charts: developer_commits.png, developer_rework.png, developer_repo_dist.png"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Add BITBUCKET_REPOS config | 2 min |
| 2 | Add get_all_commits() method | 5 min |
| 3 | Add get_commit_diff_stats() method | 5 min |
| 4 | Add name matching functions | 3 min |
| 5 | Add rework classification function | 3 min |
| 6 | Add main data collection function | 5 min |
| 7 | Add chart generation function | 5 min |
| 8 | Add CLI integration | 3 min |
| 9 | Integration testing | 10 min |

**Total: ~41 minutes**
