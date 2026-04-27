# Extract Configuration Tables to YAML Files

## Goal

Move hardcoded configuration tables (`COMPONENTS`, `BITBUCKET_REPOS`, `TESTERS`, `VALID_DEVELOPERS`) from `jira_info.py` to external YAML files for easier maintenance.

## File Structure

```
schedule/
├── components.yaml    # COMPONENTS + BITBUCKET_REPOS
├── team.yaml          # TESTERS + VALID_DEVELOPERS  
└── jira_info.py       # imports from YAML files
```

## YAML File Formats

### components.yaml

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
  # ... additional components

bitbucket_repos:
  - project: "FSSRPT"
    slug: "des"
    name: "DES"
  - project: "FSSRPT"
    slug: "csv"
    name: "CSV"
  # ... additional repos
```

### team.yaml

```yaml
testers:
  - "Allen Lai"
  - "Henrik Schneider"
  - "Michael Olstad"
  - "Ryan Patz"

developers:
  - "Minal"
  - "Isabel"
  - "Dennis"
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
  - "Sabrish"
  - "Padma"

```

## Loading Logic

Add to `jira_info.py` near the top (after imports):

```python
import yaml
from pathlib import Path

def _load_yaml_config(filename):
    """Load a YAML config file from the same directory as this script."""
    config_path = Path(__file__).parent / filename
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Load configuration from YAML files
_components_config = _load_yaml_config('components.yaml')
_team_config = _load_yaml_config('team.yaml')

COMPONENTS = _components_config['components']
BITBUCKET_REPOS = _components_config['bitbucket_repos']
TESTERS = _team_config['testers']
VALID_DEVELOPERS = _team_config['developers']
```

## Changes to jira_info.py

1. Add `import yaml` and `from pathlib import Path` to imports
2. Add `_load_yaml_config()` helper function
3. Replace the four hardcoded lists with YAML loading code
4. Remove the old inline definitions of `COMPONENTS`, `BITBUCKET_REPOS`, `TESTERS`, `VALID_DEVELOPERS`

## Dependencies

Add `pyyaml` to the project dependencies. Update CLAUDE.md to include:

```bash
pip install pandas plotly kaleido openpyxl requests pyyaml
```

## Error Handling

- Missing YAML file: `FileNotFoundError` with path in message
- Malformed YAML: `yaml.YAMLError` propagates with parse error details

## Testing

1. Run `python jira_info.py --help` to verify module loads
2. Run existing functionality to ensure data loads correctly
3. Verify YAML files are valid by loading them independently
