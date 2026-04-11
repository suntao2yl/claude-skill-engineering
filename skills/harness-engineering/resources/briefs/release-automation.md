# Release Automation Reference

Patterns for executable release automation steps in release-checklist.json.

## Step Types

### run_tests
```json
{"step": "run_tests", "command": "python3 -m pytest", "expected": "", "output": "", "status": "pending"}
```
Run the full test suite. Expected can be empty (just checks exit code 0).

### version_bump
```json
{"step": "version_bump", "command": "echo '0.3.0' > VERSION", "expected": "", "output": "", "status": "pending"}
```
Update the version file. Adapt command to project's versioning scheme.

### changelog_update
```json
{"step": "changelog_update", "command": "head -5 CHANGELOG.md", "expected": "contains '0.3.0'", "output": "", "status": "pending"}
```
Verify CHANGELOG was updated. The command should check the file, not write it (writing is done by the executor before recording the step).

### create_tag
```json
{"step": "create_tag", "command": "git tag v0.3.0", "expected": "", "output": "", "status": "pending"}
```
Create a git tag. The tagged_commit field in the artifact should match.

### create_pr
```json
{"step": "create_pr", "command": "gh pr create --title 'Release v0.3.0' --body 'Release notes...'", "expected": "", "output": "", "status": "pending"}
```
Create a pull request. Requires `gh` CLI. Skip if not applicable.

## Execution Pattern

1. Executor fills each step's command field
2. Executor runs each command and records output + status (done/failed/skipped)
3. engineering_advance.py re-executes commands to verify
4. Failed steps block advance with REL-006 error code

## Adapting to Project

Not all steps apply to every project. Skip steps that don't make sense:
- No version file? Skip version_bump
- No CHANGELOG? Skip changelog_update
- No GitHub? Skip create_pr

Set skipped steps' status to "skipped" with a notes field explaining why.
