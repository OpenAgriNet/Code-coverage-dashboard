# Per-Branch Coverage and Security Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard into one simple table per branch set — repository, code coverage, security status — where the branch to monitor is configured per repository, plus a table for the latest release.

**Architecture:** `config/repos.json` gains a per-repo branch (and optional security workflow file). `scripts/aggregate_coverage.py` measures coverage and security for exactly that branch and writes `data/coverage.json`. `index.html` renders a three-column table using live Codecov and GitHub Actions badge images, with the line counts from the data file underneath. A second section repeats this for each repo's latest `release-*` branch.

**Tech Stack:** Python 3.12 + `requests` (existing), pytest (new, tests only), static HTML/JS (existing), GitHub Actions + Pages (existing).

**Spec:** Meeting "Repo Dashboard", 2026-10-15 (Kushagra Gupta, Yaseen Ahmad, Kelvin Prabhu). Requirements extracted below.

## Requirements from the meeting

1. One simple table: column 1 repository name, column 2 code coverage %, column 3 security status (passing/failing). "That's it."
2. Show **development status**, not release status: the branch where active development happens.
3. The branch is **configurable per repository** (network-adapter → `development`; AI repos with no development branch → `main`). No naming convention is imposed on repos.
4. Keep the "lines covered" detail ("this is also good").
5. Show coverage and security as the same **badge images** used in the READMEs (Codecov badge, GitHub Actions security badge).
6. **Remove the extra information**: commit counts, branch activity, latest merged PR, development-branch column.
7. Later: **separate tables per release** (release 0.1, 0.2 …), or one for the latest release (possibly a `release-latest` tag).
8. Refresh: the 6-hour schedule stays; add or keep an on-demand trigger.

## Facts checked on 2026-10-15 (affect what the table can show)

- The badges seen in the meeting on network-adapter's `development` README point at **`release-0.0.1`**, not `development`:
  `codecov.io/gh/OpenAgriNet/network-adapter/branch/release-0.0.1/graph/badge.svg` and `.../workflows/security.yml/badge.svg?branch=release-0.0.1`. discovery-service is the same.
- For the `development` branch those same badges return **"unknown"** (Codecov) and **"no status"** (Security), because in network-adapter and discovery-service `coverage.yml` and `security.yml` only run on `push: [main, release-*]`. Codecov has no `development` data for any repo.
- experience-api and experience-ui have **no `security.yml`**. helmcharts and infra-automation have no coverage.
- knowledge-provider and decision-support-system run `security.yml` on `main` (decision-support-system is passing today); their Codecov badges work without the `?token=` parameter.

**Consequence:** until network-adapter and discovery-service add `development` to the `push.branches` of `coverage.yml` and `security.yml`, a `development` row shows "No report" and "No runs". The dashboard must show that plainly, not as 0% or failing. This is a team decision outside this repo (Open question 1).

## Global Constraints

- No Claude co-author or attribution in commits or PR descriptions.
- Never `git push`; commit locally. The repo owner pushes.
- Work on a new branch from an up-to-date `main` (`git fetch origin && git checkout -B feat/branch-coverage-security origin/main`). Local `main` is currently stale at `17cffa5`; do not build on it.
- Only public repositories are published (keep the existing public-only rule for project-discovered repos).
- "No report" never means 0%; "No runs" never means failing.
- Keep the code style of `scripts/aggregate_coverage.py` (single-space indent, compact one-liners).

## Review Focus

1. A configured branch that does not exist in the repo (typo, renamed): row shows "Branch not found", not a crash or an empty row. Test in Task 1.
2. A security workflow that has never run on the configured branch: status "No runs", badge still shown, not "failing". Test in Task 2.
3. A repo with no `security.yml` at all (experience-api): status "No security workflow". Test in Task 2.
4. A repo listed as a plain string in config (old format) still works and uses its default branch. Test in Task 1.
5. A repo with no `release-*` branch: it is left out of the release table rather than shown as an empty row. Test in Task 4.

---

## File Structure

- Modify `config/repos.json`: `repositories` becomes a list of objects `{name, branch, security_workflow}`; strings still accepted. Add `release_branch_prefix`. Remove `dev_branch_names` and `activity_days`.
- Modify `scripts/aggregate_coverage.py`: add `repo_targets()`, `security_status()`, `latest_release_branch()`; rewrite `inspect()`; delete `details()` and the development-branch logic.
- Create `tests/test_aggregate.py`: pytest unit tests with GitHub/Codecov calls stubbed.
- Create `requirements-dev.txt`: `pytest`, `requests`.
- Modify `index.html`: three-column tables (Development, Latest release); remove the extra-details toggle, columns and filters.
- Modify `README.md`: resolve the leftover merge-conflict markers; document the config format and the branch caveat.

---

### Task 1: Per-repository branch configuration

**Files:**
- Modify: `config/repos.json`
- Modify: `scripts/aggregate_coverage.py` (`main()`, new `repo_targets()`)
- Create: `tests/test_aggregate.py`, `requirements-dev.txt`

**Interfaces:**
- Produces: `repo_targets(cfg: dict, dpg: list[str]) -> list[dict]`. Each item is `{'name': str, 'branch': str|None, 'security_workflow': str}`. `branch=None` means "use the repo's default branch".

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aggregate.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import aggregate_coverage as a

def test_repo_targets_mixes_objects_strings_and_project_repos():
    cfg = {'repositories': [{'name': 'network-adapter', 'branch': 'development'}, 'knowledge-provider'],
           'exclude_repositories': ['engineering-tracker']}
    got = a.repo_targets(cfg, ['network-adapter', 'helmcharts', 'engineering-tracker'])
    assert got == [
        {'name': 'network-adapter', 'branch': 'development', 'security_workflow': 'security.yml'},
        {'name': 'knowledge-provider', 'branch': None, 'security_workflow': 'security.yml'},
        {'name': 'helmcharts', 'branch': None, 'security_workflow': 'security.yml'},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pip install -r requirements-dev.txt && python -m pytest tests/test_aggregate.py -v`
Expected: FAIL with `AttributeError: module 'aggregate_coverage' has no attribute 'repo_targets'`

- [ ] **Step 3: Write minimal implementation**

`requirements-dev.txt`:
```
pytest==8.3.3
requests==2.32.3
```

In `scripts/aggregate_coverage.py`, add above `def main():`
```python
def repo_targets(cfg,dpg):
 """Configured repos (objects or plain names) plus project-discovered ones, minus exclusions; first entry wins."""
 skip=set(cfg.get('exclude_repositories',[]));out={}
 for e in cfg.get('repositories',[])+list(dpg):
  e={'name':e} if isinstance(e,str) else dict(e)
  if e['name'] in skip or e['name'] in out:continue
  out[e['name']]={'name':e['name'],'branch':e.get('branch'),'security_workflow':e.get('security_workflow','security.yml')}
 return list(out.values())
```
and in `main()` replace
```python
 CFG['dpg_repositories']=dpg;skip=set(CFG.get('exclude_repositories',[]))
 repos=[r for r in dict.fromkeys(CFG.get('repositories',[])+dpg) if r not in skip]
 results=[inspect(r) for r in repos]
```
with
```python
 CFG['dpg_repositories']=dpg
 results=[inspect(t) for t in repo_targets(CFG,dpg)]
```

`config/repos.json` `repositories` (branches to confirm with the team, Open question 2):
```json
"repositories": [
  {"name": "network-adapter", "branch": "development"},
  {"name": "discovery-service", "branch": "development"},
  {"name": "helmcharts", "branch": "development"},
  {"name": "decision-support-system", "branch": "main"},
  {"name": "knowledge-provider", "branch": "main"},
  {"name": "experience-api", "branch": "main"},
  {"name": "experience-ui", "branch": "main"},
  {"name": "infra-automation", "branch": "main"}
],
"release_branch_prefix": "release-",
```
Delete the `dev_branch_names` and `activity_days` keys.

- [ ] **Step 4: Add the old-format and missing-branch tests (Review Focus 1, 4)**

```python
def test_plain_string_entry_uses_default_branch():
    assert a.repo_targets({'repositories': ['x']}, [])[0]['branch'] is None

def test_resolve_branch_reports_missing_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda path: None)  # GitHub 404 for the branch
    assert a.resolve_branch('network-adapter', 'devlopment') == ('devlopment', False)
```
and add to the script:
```python
def resolve_branch(repo,branch):
 """(branch, exists). None means the repo's default branch."""
 if not branch:return default_branch(repo),True
 return branch,bool(api(f'/repos/{ORG}/{repo}/branches/{branch}'))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add config/repos.json scripts/aggregate_coverage.py tests/test_aggregate.py requirements-dev.txt
git commit -m "Configure the monitored branch per repository"
```

---

### Task 2: Security status per branch

**Files:**
- Modify: `scripts/aggregate_coverage.py` (new `security_status()`)
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: `api(path)` (existing; returns `None` on 404).
- Produces: `security_status(repo: str, branch: str, workflow: str) -> dict` with keys `state` (`'passing'|'failing'|'no runs'|'no workflow'`), `run_url` (str|None), `badge_url` (str|None), `finished_at` (str|None).

- [ ] **Step 1: Write the failing tests (Review Focus 2, 3)**

```python
def fake_api(responses):
    return lambda path: next((v for k, v in responses.items() if path.startswith(k)), None)

def test_security_passing(monkeypatch):
    monkeypatch.setattr(a, 'api', fake_api({
        '/repos/OpenAgriNet/dss/actions/workflows/security.yml/runs': {'workflow_runs': [
            {'status': 'completed', 'conclusion': 'success', 'html_url': 'u', 'updated_at': 't'}]},
        '/repos/OpenAgriNet/dss/actions/workflows/security.yml': {'id': 1}}))
    s = a.security_status('dss', 'main', 'security.yml')
    assert s['state'] == 'passing' and s['run_url'] == 'u'
    assert s['badge_url'] == 'https://github.com/OpenAgriNet/dss/actions/workflows/security.yml/badge.svg?branch=main'

def test_security_never_ran_on_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', fake_api({
        '/repos/OpenAgriNet/na/actions/workflows/security.yml/runs': {'workflow_runs': []},
        '/repos/OpenAgriNet/na/actions/workflows/security.yml': {'id': 1}}))
    assert a.security_status('na', 'development', 'security.yml')['state'] == 'no runs'

def test_security_workflow_missing(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda path: None)
    s = a.security_status('experience-api', 'main', 'security.yml')
    assert s['state'] == 'no workflow' and s['badge_url'] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_aggregate.py -k security -v`
Expected: FAIL with `AttributeError: ... no attribute 'security_status'`

- [ ] **Step 3: Write minimal implementation**

```python
def security_status(repo,branch,workflow):
 """Latest completed run of the security workflow on `branch`."""
 out={'state':'no workflow','run_url':None,'badge_url':None,'finished_at':None}
 if not api(f'/repos/{ORG}/{repo}/actions/workflows/{workflow}'):return out
 out['badge_url']=f'https://github.com/{ORG}/{repo}/actions/workflows/{workflow}/badge.svg?branch={branch}'
 runs=(api(f'/repos/{ORG}/{repo}/actions/workflows/{workflow}/runs?branch={branch}&status=completed&per_page=1') or {}).get('workflow_runs',[])
 if not runs:out['state']='no runs';return out
 r=runs[0];out.update(state='passing' if r.get('conclusion')=='success' else 'failing',run_url=r.get('html_url'),finished_at=r.get('updated_at'))
 return out
```
Note: the `/runs` key must be checked before the bare workflow key in `fake_api` because both share a prefix; the dict order in the tests already does this.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate_coverage.py tests/test_aggregate.py
git commit -m "Report security workflow status for the monitored branch"
```

---

### Task 3: Simplified per-repo record (drop extra details)

**Files:**
- Modify: `scripts/aggregate_coverage.py` (`inspect()`; delete `details()` and the development-branch code)
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: `resolve_branch()` (Task 1), `security_status()` (Task 2), `branch_coverage()` (existing).
- Produces: each item of `data/coverage.json` `repositories`:
  `{repository, html_url, dpg, branch, branch_exists, coverage, coverage_source, coverage_commit, coverage_detail, coverage_badge_url, measured_at, security}`.

- [ ] **Step 1: Write the failing test**

```python
def test_inspect_record_shape(monkeypatch):
    monkeypatch.setattr(a, 'resolve_branch', lambda r, b: ('development', True))
    monkeypatch.setattr(a, 'branch_coverage', lambda r, b: {'coverage': 74.35, 'source': 'Codecov', 'commit': 'abc',
        'detail': {'lines': 10, 'hits': 7, 'files': 1, 'report_url': 'x'}, 'measured_at': 't'})
    monkeypatch.setattr(a, 'security_status', lambda r, b, w: {'state': 'failing'})
    rec = a.inspect({'name': 'network-adapter', 'branch': 'development', 'security_workflow': 'security.yml'})
    assert rec['branch'] == 'development' and rec['coverage'] == 74.35 and rec['security']['state'] == 'failing'
    assert rec['coverage_badge_url'] == 'https://codecov.io/gh/OpenAgriNet/network-adapter/branch/development/graph/badge.svg'
    assert 'last_merged_pr' not in rec and 'main_commits_recent' not in rec and 'dev_coverage' not in rec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_aggregate.py::test_inspect_record_shape -v`
Expected: FAIL (`inspect()` takes a string and returns the old shape)

- [ ] **Step 3: Write minimal implementation**

Replace the whole `def inspect(repo):` function with:
```python
def inspect(t):
 repo=t['name'];url=f'https://github.com/{ORG}/{repo}';branch,exists=resolve_branch(repo,t.get('branch'))
 out={'repository':repo,'html_url':url,'dpg':repo in CFG.get('dpg_repositories',[]),'branch':branch,'branch_exists':exists,
  'coverage':None,'coverage_source':'Branch not found','coverage_commit':None,'coverage_detail':None,
  'coverage_badge_url':f'https://codecov.io/gh/{ORG}/{repo}/branch/{branch}/graph/badge.svg','measured_at':None,
  'security':{'state':'branch not found','run_url':None,'badge_url':None,'finished_at':None}}
 if not exists:return out
 m=branch_coverage(repo,branch)
 out.update(coverage=m['coverage'],coverage_source=m['source'],coverage_commit=m['commit'],coverage_detail=m['detail'],measured_at=m['measured_at'],
  security=security_status(repo,branch,t.get('security_workflow','security.yml')))
 return out
```
Delete `def details(...)` entirely and the `default_branch`-based `devs` logic. Keep `branch_coverage()`, `codecov()`, `commit_date()`, `parse()`, `xml_pct()`, `dpg_project_repos()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: 7 passed

- [ ] **Step 5: Smoke-run against real repos (read-only)**

Run: `GH_TOKEN=<your read-only token> python scripts/aggregate_coverage.py && python -c "import json;[print(r['repository'],r['branch'],r['coverage'],r['security']['state']) for r in json.load(open('data/coverage.json'))['repositories']]"`
Expected today: network-adapter `development None no runs`; decision-support-system `main 96.04 passing` (coverage value may differ).
Then `git checkout -- data/coverage.json` so local data is not committed.

- [ ] **Step 6: Commit**

```bash
git add scripts/aggregate_coverage.py tests/test_aggregate.py
git commit -m "Measure coverage and security for the configured branch only; drop extra details"
```

---

### Task 4: Latest-release table data

**Files:**
- Modify: `scripts/aggregate_coverage.py` (new `latest_release_branch()`, `main()` writes `releases`)
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Produces: `latest_release_branch(repo: str, prefix: str) -> str|None` (highest version, e.g. `release-0.0.2` over `release-0.0.1`); `data/coverage.json` gains `releases: [record, ...]` using the Task 3 record shape.

- [ ] **Step 1: Write the failing tests (Review Focus 5)**

```python
def test_latest_release_picks_highest_version(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda p: [{'name': 'release-0.0.9'}, {'name': 'release-0.0.10'}, {'name': 'main'}])
    assert a.latest_release_branch('na', 'release-') == 'release-0.0.10'

def test_latest_release_none_when_no_release_branch(monkeypatch):
    monkeypatch.setattr(a, 'api', lambda p: [{'name': 'main'}])
    assert a.latest_release_branch('kp', 'release-') is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_aggregate.py -k release -v`
Expected: FAIL with `AttributeError: ... no attribute 'latest_release_branch'`

- [ ] **Step 3: Write minimal implementation**

```python
def latest_release_branch(repo,prefix):
 names=[b['name'] for b in (api(f'/repos/{ORG}/{repo}/branches?per_page=100') or []) if b['name'].startswith(prefix)]
 key=lambda n:[int(x) if x.isdigit() else x for x in re.split(r'[.\-]',n[len(prefix):])]
 return max(names,key=key) if names else None
```
In `main()`, after `results=...`:
```python
 prefix=CFG.get('release_branch_prefix','release-');releases=[]
 for t in repo_targets(CFG,dpg):
  rb=latest_release_branch(t['name'],prefix)
  if rb:releases.append(inspect({**t,'branch':rb}))
```
and write `'releases':releases` into the JSON next to `'repositories':results`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate_coverage.py tests/test_aggregate.py
git commit -m "Add latest-release coverage and security data"
```

---

### Task 5: Simple three-column UI with badges

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `data/coverage.json` `repositories` and `releases` (Tasks 3–4).

- [ ] **Step 1: Replace the table markup**

Remove: the "Branch activity and PRs" checkbox, the three `.extra` columns, the `dev`/`nodev`/`failed` filter options, the `activity-desc`/`pr-desc` sort options, the "Latest CI" and "Measured" columns. Render two sections with the same table:

```html
<section aria-labelledby="dev-title">
  <h2 id="dev-title">Development</h2>
  <p class="sub">Each repository's working branch, set in <code>config/repos.json</code>.</p>
  <div class="table-wrap"><table><thead><tr><th>Repository</th><th>Code coverage</th><th>Security</th></tr></thead><tbody id="dev-rows"></tbody></table></div>
</section>
<section aria-labelledby="rel-title">
  <h2 id="rel-title">Latest release</h2>
  <div class="table-wrap"><table><thead><tr><th>Repository</th><th>Code coverage</th><th>Security</th></tr></thead><tbody id="rel-rows"></tbody></table></div>
</section>
```

- [ ] **Step 2: Replace the row renderer**

```js
function row(r){
  const url=repoUrl(r),cd=r.coverage_detail||{},s=r.security||{};
  const cov=r.branch_exists===false?'<span class="muted">Branch not found</span>'
    :`<a href="${esc(cd.report_url||url)}" target="_blank" rel="noopener"><img src="${esc(r.coverage_badge_url)}" alt="Coverage ${isNum(r.coverage)?(+r.coverage).toFixed(2)+'%':'unknown'}" height="20"></a>`
     +(cd.lines?`<div class="sub">${num(cd.hits)} of ${num(cd.lines)} lines covered</div>`:isNum(r.coverage)?'':'<div class="sub">No report on this branch</div>');
  const label={passing:'Passing',failing:'Failing','no runs':'No runs on this branch','no workflow':'No security workflow','branch not found':'Branch not found'}[s.state]||'Unknown';
  const sec=s.badge_url?`<a href="${esc(s.run_url||url+'/actions')}" target="_blank" rel="noopener"><img src="${esc(s.badge_url)}" alt="Security ${label}" height="20"></a>`:`<span class="muted">${label}</span>`;
  return `<tr><td><a class="repo" href="${esc(url)}/tree/${esc(r.branch)}" target="_blank" rel="noopener">${esc(r.repository)}</a> ${dpgTag(r)}<div class="sub">${esc(r.branch)}</div></td><td>${cov}</td><td>${sec}</td></tr>`;
}
```
In `init()`: `$('dev-rows').innerHTML=(d.repositories||[]).map(row).join('')||empty`; same for `rel-rows` with `d.releases`. Keep the search box filtering both tables by name. Update the summary sentence to count `passing` security and repos with coverage.

- [ ] **Step 3: Update "How coverage is measured"**

Replace the Branches bullet with: "**Branch.** Set per repository in `config/repos.json` (for example `development` for network-adapter, `main` for the AI repos). The latest-release table uses each repo's highest `release-*` branch." Add: "**Security.** The latest completed run of the repo's `security.yml` on that branch. *No runs* means the workflow does not run on that branch — it is not a failure."

- [ ] **Step 4: Verify in a browser**

Run: `python -m http.server 8000` with a `data/coverage.json` produced by Task 3 Step 5, open `http://localhost:8000`.
Expected: two tables, three columns each; network-adapter `development` shows the Codecov "unknown" badge with "No report on this branch" and Security "No runs on this branch" (as text or "no status" badge); decision-support-system shows a coverage badge and a "passing" security badge; no horizontal page scroll at 390px width; light and dark themes readable.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Show coverage and security badges per configured branch and latest release"
```

---

### Task 6: README and refresh trigger

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/deploy.yml` (only if Open question 4 is answered "yes")

- [ ] **Step 1: Resolve the merge-conflict markers in `README.md`**

Delete the `<<<<<<< HEAD`, `=======` and `>>>>>>> 327392c ...` lines and the duplicated two-line intro; keep the longer section.

- [ ] **Step 2: Document configuration**

Add a "Choosing the branch per repository" section with the `repositories` object format from Task 1, the `security_workflow` override, `release_branch_prefix`, and the note: "Coverage and security only exist for a branch if that repo's `coverage.yml` / `security.yml` run on pushes to it."

- [ ] **Step 3: Refresh on demand**

`workflow_dispatch` already exists ("Run workflow" button). Badge images are fetched live by the browser, so the badges are always current; only line counts and run links wait for the 6-hour refresh. Document this. If the team wants refresh on every push in the tracked repos, that needs a `repository_dispatch` sender in each repo — record as follow-up, not in this plan.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Document per-branch configuration and refresh behaviour"
```

---

## Open questions for the team (decide before Task 1 config is final)

1. **Development branches have no data today.** network-adapter and discovery-service run `coverage.yml` and `security.yml` only on `main` and `release-*` (by documented choice). Their `development` rows will show "No report" / "No runs" until those repos add `development` to `on.push.branches`. Who asks the maintainers?
2. **Branch per repo.** Proposed: network-adapter, discovery-service, helmcharts → `development`; decision-support-system, knowledge-provider, experience-api, experience-ui, infra-automation → `main`. Confirm.
3. **Release table.** Latest `release-*` branch per repo (this plan), or a `release-latest` tag once it exists, or one table per release version?
4. **Refresh.** Keep 6-hour schedule + manual button, or also refresh on every push to this dashboard repo only (already the case)?
5. **Repos without a security workflow** (experience-api, experience-ui): show "No security workflow", or hide the row until they add one?
