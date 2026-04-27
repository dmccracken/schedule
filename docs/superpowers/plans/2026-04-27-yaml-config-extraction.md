# YAML Configuration Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract hardcoded configuration tables (COMPONENTS, BITBUCKET_REPOS, TESTERS, VALID_DEVELOPERS) from jira_info.py to external YAML files.

**Architecture:** Create two YAML files - `components.yaml` (project config) and `team.yaml` (people config). Add a helper function to load YAML files at module import time. Remove inline definitions from jira_info.py.

**Tech Stack:** Python, PyYAML

---

## File Structure

```
schedule/
├── components.yaml     # Create: COMPONENTS + BITBUCKET_REPOS
├── team.yaml           # Create: TESTERS + VALID_DEVELOPERS
├── jira_info.py        # Modify: add YAML loading, remove inline definitions
└── CLAUDE.md           # Modify: add pyyaml to dependencies
```

---

### Task 1: Create components.yaml

**Files:**
- Create: `components.yaml`

- [ ] **Step 1: Create components.yaml with all component and repo data**

Create file `components.yaml`:

```yaml
components:
  - component: "Alarms Dashboard"
    name: "Alarm Dashboard"
    version: "Alarm_26.01"
    release_notes: "https://apg-bb.amat.com/projects/FSSRPT/repos/alarm_dispatch/browse/Alarm_Comprehensive_Service/scripts/ReleaseNotes.txt"
  - component: "AutoUVA"
    name: "AutoUVA Dashboard"
    version: "AUTO_UVA_26.05"
    release_notes: "https://apg-bb.amat.com/projects/FSSRPT/repos/trace_segmentation/browse/Auto_Uva_Comprehensive_Service/scripts/ReleaseNotes.txt"
  - component: "CSV"
    name: "CSV Dashboard"
    version: "CSV_26.01"
    release_notes: "https://apg-bb.amat.com/projects/FSSRPT/repos/csv/browse/CSV_Comprehensive_Service/scripts/ReleaseNotes.txt"
  - component: "DES"
    name: "DES Dashboard"
    version: "DES_V2"
    release_notes: null
  - component: "DES"
    name: "DES Dashboard"
    version: "DES_V26.05"
    release_notes: null
  - component: "PPTS"
    name: "PPTS Dashboard"
    version: "PPTS_26.03"
    release_notes: "https://apg-bb.amat.com/projects/FSSRPT/repos/pts_dashboard/browse/ReleaseNotes.txt"
  - component: "PPTS"
    name: "PPTS Dashboard"
    version: "PPTS_26.07"
    release_notes: "https://apg-bb.amat.com/projects/FSSRPT/repos/pts_dashboard/browse/ReleaseNotes.txt"
  - component: "ToolConnection"
    name: "ToolConnection Dashboard"
    version: "Toolconnection2.0"
    release_notes: null
  - component: "Guardband"
    name: "Guardband Dashboard"
    version: null
    release_notes: null
  - component: "EPD Dashboard"
    name: "EPD Dashboard"
    version: null
    release_notes: null
  - component: "PdM Dashboard"
    name: "PdM Dashboard"
    version: null
    release_notes: null

bitbucket_repos:
  - project: "FSSRPT"
    slug: "des"
    name: "DES"
  - project: "FSSRPT"
    slug: "csv"
    name: "CSV"
  - project: "FSSRPT"
    slug: "trace_segmentation"
    name: "Trace Segmentation"
  - project: "FSSRPT"
    slug: "alarm_dispatch"
    name: "Alarm Dispatch"
  - project: "FSSRPT"
    slug: "tool_connection_control_app"
    name: "Tool Connection"
  - project: "FSSRPT"
    slug: "pts_dashboard"
    name: "PTS Dashboard"
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('components.yaml'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add components.yaml
git commit -m "feat: add components.yaml with COMPONENTS and BITBUCKET_REPOS"
```

---

### Task 2: Create team.yaml

**Files:**
- Create: `team.yaml`

- [ ] **Step 1: Create team.yaml with testers and developers**

Create file `team.yaml`:

```yaml
testers:
  - "Allen Lai"
  - "Henrik Schneider"
  - "Michael Olstad"
  - "Ryan Patz"
  - "Dennis"
  - "Minal"

developers:
  - "Hemalatha Mallala"
  - "Hemalatha Nallanna Gari"
  - "NAGARAJ B S"
  - "Roshini Jayalakshmi"
  - "SNEHA HA"
  - "Shashivardhan Manne"
  - "Pavithra"
  - "Tannu"
  - "Lundi"
  - "Prajwal"
  - "Ramyaa"
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('team.yaml'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add team.yaml
git commit -m "feat: add team.yaml with TESTERS and VALID_DEVELOPERS"
```

---

### Task 3: Add YAML loading to jira_info.py

**Files:**
- Modify: `jira_info.py:9-18` (imports section)

- [ ] **Step 1: Add yaml import and Path import**

In `jira_info.py`, after line 17 (`from requests.auth import HTTPBasicAuth`), add:

```python
import yaml
from pathlib import Path
```

- [ ] **Step 2: Add _load_yaml_config helper function**

After the imports (before `class BitBucketClient:`), add:

```python

def _load_yaml_config(filename):
    """Load a YAML config file from the same directory as this script."""
    config_path = Path(__file__).parent / filename
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Load configuration from YAML files
_components_config = _load_yaml_config("components.yaml")
_team_config = _load_yaml_config("team.yaml")

COMPONENTS = _components_config["components"]
BITBUCKET_REPOS = _components_config["bitbucket_repos"]
TESTERS = _team_config["testers"]
VALID_DEVELOPERS = _team_config["developers"]

```

- [ ] **Step 3: Verify module loads**

Run: `python -c "import jira_info; print(len(jira_info.COMPONENTS), len(jira_info.BITBUCKET_REPOS), len(jira_info.TESTERS), len(jira_info.VALID_DEVELOPERS))"`
Expected: `11 6 6 11`

- [ ] **Step 4: Commit**

```bash
git add jira_info.py
git commit -m "feat: add YAML config loading to jira_info.py"
```

---

### Task 4: Remove inline definitions from jira_info.py

**Files:**
- Modify: `jira_info.py:1167-1275` (remove COMPONENTS, BITBUCKET_REPOS, TESTERS, VALID_DEVELOPERS definitions)

- [ ] **Step 1: Delete the COMPONENTS list definition**

Remove lines 1167-1240 (the entire `COMPONENTS = [...]` block).

- [ ] **Step 2: Delete the BITBUCKET_REPOS list definition**

Remove lines 1242-1250 (the entire `BITBUCKET_REPOS = [...]` block including the comment).

- [ ] **Step 3: Delete the TESTERS list definition**

Remove lines 1252-1260 (the entire `TESTERS = [...]` block including the comment).

- [ ] **Step 4: Delete the VALID_DEVELOPERS list definition**

Remove lines 1262-1275 (the entire `VALID_DEVELOPERS = [...]` block including the comment).

- [ ] **Step 5: Verify module still loads correctly**

Run: `python -c "import jira_info; print(len(jira_info.COMPONENTS), len(jira_info.BITBUCKET_REPOS), len(jira_info.TESTERS), len(jira_info.VALID_DEVELOPERS))"`
Expected: `11 6 6 11`

- [ ] **Step 6: Verify help works**

Run: `python jira_info.py --help`
Expected: Help text displays without errors

- [ ] **Step 7: Commit**

```bash
git add jira_info.py
git commit -m "refactor: remove inline config definitions, now loaded from YAML"
```

---

### Task 5: Update CLAUDE.md dependencies

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update pip install command to include pyyaml**

In `CLAUDE.md`, find the dependencies section and change:

```bash
pip install pandas plotly kaleido openpyxl requests
```

to:

```bash
pip install pandas plotly kaleido openpyxl requests pyyaml
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add pyyaml to dependencies"
```

---

### Task 6: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Verify YAML files load independently**

Run: `python -c "import yaml; c = yaml.safe_load(open('components.yaml')); t = yaml.safe_load(open('team.yaml')); print('components:', len(c['components']), 'repos:', len(c['bitbucket_repos']), 'testers:', len(t['testers']), 'devs:', len(t['developers']))"`
Expected: `components: 11 repos: 6 testers: 6 devs: 11`

- [ ] **Step 2: Verify jira_info.py help command works**

Run: `python jira_info.py --help`
Expected: Help text displays without errors, shows all CLI options

- [ ] **Step 3: Verify data matches original**

Run: `python -c "import jira_info; print([c['component'] for c in jira_info.COMPONENTS])"`
Expected: `['Alarms Dashboard', 'AutoUVA', 'CSV', 'DES', 'DES', 'PPTS', 'PPTS', 'ToolConnection', 'Guardband', 'EPD Dashboard', 'PdM Dashboard']`
