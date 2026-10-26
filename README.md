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
- **Latest release**: each repository's newest stable version, with a dropdown of all its versions (see "Finding releases"). Repos with no version are left out.

## Choosing repositories

`config/repos.json` has three parts. Everything else in the file is a global setting (`workflow_names`, `artifact_name_hints`, `defaults.security_workflow`, `releases`).

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

The same repo listed twice under `repositories`, an unknown source `type`, or a mistyped value stops the run with a message naming the entry. The old keys `dpg_repositories`, `dpg_project`, `dpg_source`, `exclude_repositories` and `release_branch_prefix` are no longer read, and the error tells you what replaces them.

## Finding releases

Releases can exist as release branches, git tags, GitHub Releases, or a mix. The `releases` block says where to look:

```json
"releases": {
  "sources": ["branch", "tag", "release"],
  "branch_prefix": "release-",
  "tag_pattern": "^v?(?P<version>\\d+(?:\\.\\d+)*(?:-[0-9A-Za-z.]+)?)$",
  "include_prereleases": true,
  "max_versions": 10
}
```

| Setting | Meaning |
|---|---|
| `sources` | Which of `branch`, `tag`, `release` (GitHub Releases, drafts ignored) to read. The order decides which one is **measured** when a version exists in several |
| `branch_prefix` | Branches named `<prefix><version>` count as releases |
| `tag_pattern` | Regex for tag and release names. It needs a named group `version`. The default accepts `1.2.0`, `v1.2.0`, `v1.2.0-RC1` |
| `include_prereleases` | `false` hides `-RC1`-style versions and GitHub pre-releases |
| `max_versions` | Newest N versions are measured and listed; the table says when older ones are left out |

- **One version, many names.** `v0.1.0`, `0.1.0` and `release-0.1.0` are the same version `0.1.0`. Names that are not versions (for example the tag `fork-point`) are ignored. Versions are compared as numbers (`0.0.10` is newer than `0.0.9`) and a pre-release ranks below its final release.
- **What gets measured.** A branch is measured as it is now and keeps the live badges. A tag or release is measured at its tagged commit (Codecov by commit, and the security run for that commit), so it shows plain numbers and the run date instead of a badge. With the default order a version that is both a branch and a tag is measured as the branch.
- **Per repository.** Add `"releases": {...}` to a `repositories` entry to override single settings for that repo, for example `{"sources": ["tag"]}`, or `"releases": false` to leave it out of the release table. `"releases": false` at the top level turns releases off everywhere unless a repo sets its own.
- **The dropdowns.** Each repo row lists its measured versions, newest first, with the latest stable one selected. Above the table, *Show version* sets one version for every repo (repos without it say so), and *Found as* (Any, GitHub Release, Tag, Release branch) keeps only versions found that way, which also narrows the other lists.

**A branch only has data if the repository measures it.** Coverage exists only if that repo uploads to Codecov on pushes to the branch, and security status only if its `security.yml` runs on pushes to the branch. If not, the row shows an *unknown* coverage badge and *No runs on this branch*. That is not 0% and not a failure. To fix it, add the branch to `on.push.branches` in the repo's `coverage.yml` and `security.yml`.

## License policy (green, yellow, red)

List the licenses your team accepts under `licenses` in `config/repos.json`:

```json
"licenses": {
  "green":  ["MIT", "Apache-2.0", "BSD-*"],
  "yellow": ["MPL-2.0", "LGPL-*"],
  "red":    ["AGPL-*", "GPL-*", "SSPL-1.0"]
}
```

- Entries are SPDX ids or patterns (`*` matches anything), compared ignoring case. The same entry in two lists is a config error. If patterns overlap, the most restrictive class wins.
- Every repo license and dependency license gets a class: **green**, **yellow**, **red**, or **unclassified** (on no list, or an expression that cannot be read). It is shown as a coloured dot, filterable as *License risk*, and the lists are printed under the dependency table.
- Expressions follow SPDX: `A OR B` takes the better class (you may choose), `A AND B` the worse, `AND` binds tighter than `OR`, parentheses are respected, and `A WITH exception` uses the exception if you listed it, else `A`. Several licenses reported together for one package (`MIT, Apache-2.0`) are treated as all applying, so the worst counts, because deps.dev does not say whether they are alternatives.
- Nothing is blocked or failed by this. It only colours and filters. An empty policy leaves everything *unclassified*.

## Filters

Both pages share one filter component (`filters.js`).

- Tick several values in a filter to see any of them (OR). Different filters combine (AND). A filter with nothing ticked is off.
- Each option shows how many results it would give with your other filters applied. An option that would give none is greyed out, so there are no dead ends.
- Active filters appear as chips; click one to remove it, or *Clear all*. Escape closes a dropdown.
- Filters live in the address bar (`?sec=failing&tag=DPG`), so a link shares the view. A link from the main page to `deps.html?repo=network-adapter&vuln=any` opens with that repository ticked and the vulnerability filter on.
- **Main page**: one bar filters every table at once (Repository, Tag, Security, Coverage, License risk, License, Vulnerabilities, Language). Security and Coverage follow the Development/Main switch. The release table has its own *Found as* and *Stability* filters and a *Show version* selector.
- **Dependency page**: Repository, Ecosystem, License, License risk, Vulnerabilities, Update status, and a text search.
- Tests: `node --test tests/filters.test.mjs` (also run in CI before the dashboard is built).

## Stack, dependencies and vulnerabilities

`scripts/collect_stack.py` writes `data/stack.json` on every refresh. It shows each repo's license, languages and technologies, and `deps.html` lists every dependency.

| Data | Source | Authorization |
|---|---|---|
| Languages, technologies, dependencies | [specfy/stack-analyser](https://github.com/specfy/stack-analyser) on a shallow clone of the working branch | The clone uses no token and runs with an allowlisted environment, so no secret reaches the third-party code |
| Repo license | GitHub's license API | The workflow token |
| Dependency license and latest version (npm, PyPI, Go) | [deps.dev](https://deps.dev) | None, public API |
| Known vulnerabilities and the fixed version | [OSV.dev](https://osv.dev) (Google's open vulnerability database, which includes the GitHub advisories) | None: public API, no key or login. Only package names and versions are sent |

- **Main stack only.** The Stack column lists the repo's real languages and frameworks, not every file type. `stack` in `config/repos.json` controls it: `ignore_languages` and `ignore_techs` (markup, data, CI and tooling by default), `max_languages`, `max_techs`, and `min_share` (a language must be at least that share of the remaining code files; stack-analyser labels a stray `go.mod` as AMPL). Names are compared ignoring case. Languages and tools that are already implied (for example `python` as a tool next to the language Python) are in the ignore list.
- **Development / Main.** Both the stack table and `deps.html` have the same switch as the coverage tables: each repo's working branch, or its default branch. A repo whose working branch is its default branch is analysed once. The choice is remembered across the two pages and kept in the address bar (`?branch=main`).
- **"OR", commas and AND in licenses.** A license can be an SPDX expression. `Apache-2.0 OR BSD-3-Clause` (for example `cryptography`) is a real choice. Several licenses reported together (`Apache-2.0, BSD-3-Clause`, for example Go modules that contain files under both) all apply, so the policy takes the strictest; each comma-separated item is classified on its own before that. Names such as `GPL-3.0-or-later` contain "or" as part of the id and are not expressions.
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
