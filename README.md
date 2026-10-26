# OpenAgriNet Code Coverage Dashboard

A static GitHub Pages dashboard showing code coverage and security status for OpenAgriNet repositories, on the branch each repository actually develops on, plus each repository's latest release branch.

Live page: https://openagrinet.github.io/Code-coverage-dashboard/

It reads existing results only. It never checks out the tracked repositories, installs their dependencies, or reruns their tests.

## What it shows

Two tables, each with three columns:

| Column | Source |
|---|---|
| Repository | Name, the branch being measured, and a tag chip per config tag (for example DPG) |
| Code coverage | Codecov's live badge for that branch, with "N of M lines covered" from the last refresh |
| Security | Latest completed run of the repo's `security.yml` on that branch, shown as the GitHub Actions badge |

- **Development**: the branch configured per repository (see below).
- **Latest release**: each repository's highest `release-*` branch (`release-0.0.10` beats `release-0.0.9`). Repos with no release branch are left out.

## Choosing repositories

`config/repos.json` has three parts. Everything else in the file is a global setting (`workflow_names`, `artifact_name_hints`, `release_branch_prefix`, `defaults.security_workflow`).

**`repositories`**: repos you name yourself, with their branch.

```json
"repositories": [
  {"name": "network-adapter", "branch": "development"},
  {"name": "experience-api", "branch": "main", "tags": ["core"], "security_workflow": "security.yml"},
  "knowledge-provider"
]
```

- `branch` is optional; no `branch` uses the repository's default branch. A branch that does not exist shows **Branch not found**.
- `tags` are optional chips shown next to the name.
- `security_workflow` is optional and defaults to `defaults.security_workflow` (`security.yml`).

**`sources`**: ways to find repos automatically. Every repo a source finds gets that source's `tags`.

```json
"sources": [
  {"type": "query", "query": "props.project-name:\"OAN DPG\"", "tags": ["DPG"], "fallback": ["network-adapter"]},
  {"type": "project", "number": 9, "tags": ["DPG"], "enabled": false}
]
```

- `query` is a [GitHub repository search](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories) query. `org:<organization>` and `fork:true` are added for you, because search hides forks by default; set `"include_forks": false` to opt out. Custom properties are searched with `props.<name>:"<value>"`.
- `project` finds repos with an issue or PR on an org project board. It needs the `DPG_PROJECT_TOKEN` secret.
- Both accept `branch` (used for repos they find that you did not list), `enabled` (default `true`) and `fallback`, a list of repo names used if the lookup fails (rate limit, missing token), so tags do not silently disappear.
- Private repos found by a source are skipped, because the dashboard is public. List a private repo under `repositories` to track it anyway.

**`exclude`**: repo names to drop from everything.

### When the same repo turns up twice

Names are compared ignoring case.

1. A repo under `repositories` decides its own `branch` and `security_workflow`.
2. `tags` are merged: its own first, then each source's, in file order.
3. Between sources, the first one that sets a `branch` wins. A different branch from a later source is logged as `clash`.
4. `exclude` beats everything, including a listed repo.
5. A source that fails never stops the others, and the refresh log says which one and why.

The same repo listed twice under `repositories`, an unknown source `type`, or a mistyped value stops the run with a message naming the entry. The old keys `dpg_repositories`, `dpg_project`, `dpg_source` and `exclude_repositories` are no longer read, and the error tells you what replaces them.

**A branch only has data if the repository measures it.** Coverage exists only if that repo uploads to Codecov on pushes to the branch, and security status only if its `security.yml` runs on pushes to the branch. If not, the row shows an *unknown* coverage badge and *No runs on this branch*. That is not 0% and not a failure. To fix it, add the branch to `on.push.branches` in the repo's `coverage.yml` and `security.yml`.

## Stack, dependencies and vulnerabilities

`scripts/collect_stack.py` writes `data/stack.json` on every refresh. It shows each repo's license, languages and technologies, and `deps.html` lists every dependency.

| Data | Source | Authorization |
|---|---|---|
| Languages, technologies, dependencies | [specfy/stack-analyser](https://github.com/specfy/stack-analyser) on a shallow clone of the working branch | The clone uses no token and runs with an allowlisted environment, so no secret reaches the third-party code |
| Repo license | GitHub's license API | The workflow token |
| Dependency license and latest version (npm, PyPI, Go) | [deps.dev](https://deps.dev) | None, public API |
| Known vulnerabilities and the fixed version | [OSV.dev](https://osv.dev) (Google's open vulnerability database, which includes the GitHub advisories) | None: public API, no key or login. Only package names and versions are sent |

- A package is checked at the version in its manifest. For a range such as `^5.0.0` that is the lowest version the range allows, so the version actually installed may be newer and already fixed; the page says so on those rows. Exact pins (`==`, Go modules) are checked exactly.
- **Fixed in** is the single lowest version that fixes every advisory that has a fix. Advisories with no released fix are counted separately and shown as *no fix released*.
- Docker images, GitHub Actions and unpinned versions (`latest`, `${VAR}`) are listed but not checked. They show *Not checked*, which is not the same as *None known*.
- Severity is the one published with the advisory. Advisories without a rating (for example Go's) show *not rated*.
- Only direct dependencies from manifests are listed, not the full lockfile tree.

## Refreshing

The workflow `.github/workflows/deploy.yml` runs every 6 hours, on pushes to `main` that touch the dashboard, and on demand from **Actions → Refresh and deploy coverage dashboard → Run workflow**.

The coverage and security badges are loaded live by the browser, so they are always current. Only the line counts and run links wait for the next refresh.

## Secrets

| Secret | Needed for |
|---|---|
| `CODECOV_TOKEN` | Codecov API reads (public repos also work without it) |
| `DPG_PROJECT_TOKEN` | Optional. Only for a `project` source. Reads an org project board to discover repos. Classic token with `read:project`, or fine-grained with Organization → Projects: read |

The workflow's built-in `GITHUB_TOKEN` is enough for public repositories' branches, workflow runs and artifacts.

## Coverage fallback

If Codecov has nothing for the branch, the script looks for a coverage file in the artifacts of the latest successful run (of workflows named in `workflow_names`, default `CI`) on that branch. Supported: Cobertura/JaCoCo XML, LCOV, Istanbul `coverage-summary.json`, Go cover profiles.

## Local run

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
GH_TOKEN=<read-only token> python scripts/aggregate_coverage.py
python -m http.server 8000   # open http://localhost:8000
```
