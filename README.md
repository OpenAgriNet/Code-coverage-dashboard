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

- **Development**: each repository's development branch (see *Choosing repositories*).
- **Latest release**: each repository's newest stable version, with a dropdown of all its versions (see "Finding releases"). Repos with no version are left out.

## Choosing repositories

The config says only what the scripts cannot know. Repos are **found**, not listed:

```json
"sources": [{"type": "query", "query": "props.project-name:\"OAN DPG\"", "tags": ["DPG"]}],
"exclude": ["engineering-tracker", "Code-coverage-dashboard", "infra-automation", "network-specs", "protocol-specifications-v2"],
"repositories": [],
"branches": {"development": "^(dev|develop|development)$"}
```

**`sources`**: where repos come from. Every repo a source finds gets that source's `tags`.
- `query` is a [GitHub repository search](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories). `org:<organization>` and `fork:true` are added for you, because search hides forks by default (`"include_forks": false` opts out). Custom properties are searched with `props.<name>:"<value>"`.
- `project` finds repos with an issue or PR on an org project board (`"number"`, optional `"org"`). It needs the `DPG_PROJECT_TOKEN` secret. Not used by default.
- Both accept `tags` and `enabled`.
- Private repos found by a source are skipped, because the dashboard is public. A private repo added under `repositories` gets no data either: the workflow's built-in token cannot read another repository's branches, runs or code, so it would show only as its default branch with nothing measured. That is why `infra-automation` is excluded.
- **A `props.` query needs a token that can read the organization's custom properties.** The workflow's built-in token cannot. GitHub does not report an error in that case: it silently ignores the `props.` part and returns **every** repository (even a made-up value matches all of them). The refresh checks for this on every run, by asking the same question with a value no repo can have, and **stops with an error** instead of publishing the whole organization. Put a token that can read custom properties in the `DPG_QUERY_TOKEN` secret (used only for this search). A classic token with `read:org` worked in testing; for a fine-grained token use the organization permission for custom properties (read). If the refresh keeps failing after you add it, the check is telling you the token still cannot read them.
- If a source fails (rate limit, bad token) the refresh **stops with an error naming it**, nothing is published, and the dashboard keeps its last data. A query that finds nothing only logs a warning. There is no fixed fallback list.

**`exclude`**: repo names to drop, whatever finds them, even an entry under `repositories`. This is where repos such as the engineering tracker, this dashboard, a private repo the workflow cannot read, or specification-only repos with no code to measure (`network-specs`, `protocol-specifications-v2`) go.

**`repositories`**: custom additions and overrides only. A repo the sources already find needs no entry. Use an entry to add a repo the query does not find (a private one, or one outside the query), or to set something for one repo:

```json
{"name": "some-repo", "dev_branch": "integration", "tags": ["core"], "security_workflow": "scan.yml", "releases": {"sources": ["tag"]}}
```

All keys except `name` are optional. An entry is merged with whatever the sources found, and its `tags` are added to theirs.

**Branches.** There is no `branch` on a repo: the Development / Main switch on the dashboard decides.
- **Main** is the repo's default branch.
- **Development** is the repo's `dev_branch` if given, else the first branch (alphabetically) matching `branches.development`. A repo with neither has no development branch: it is left out of the Development view (the note under the switch names it) and appears under Main, so its default branch is never shown as if it were a development branch.
- A branch that does not exist (a wrong `dev_branch`) shows **Branch not found**.

**Release sets.** `release_sets` names a release across repos that version themselves differently:

```json
"release_sets": [
  {"alias": "v1", "label": "Release 1", "tags": {"network-adapter": "0.1.0", "discovery-service": "0.1.0", "knowledge-provider": "v0.1.0"}},
  {"alias": "v2", "label": "Release 2", "current": true, "tags": {"network-adapter": "0.2.0", "discovery-service": "0.2.0"}}
]
```

- `tags` maps each repo to its own tag (`0.1.0`, `v0.1.0` and `release-0.1.0` are the same version). It is matched to the versions found under `releases` below, so the tag must be a version name and within `max_versions`; otherwise the row says the tag was not found.
- One set may be marked `"current": true`; with none marked, the last one listed is current. The dashboard opens on the current set and the **Release** selector switches between sets or back to each repo's latest. Repos you did not map show *Not part of Release 2*.
- The selection is in the address bar (`?set=v1`).

**Other settings**: `coverage` (`workflow_names`, `artifact_name_hints`), `security` (`workflow`), `releases`, `stack` and `licenses` are described in their own sections. Removed keys are rejected with a message saying what replaces them: `branch` on a repo or source, `fallback`, `defaults`, `workflow_names`, `artifact_name_hints` at the top level, `dpg_repositories`, `dpg_project`, `dpg_source`, `exclude_repositories`, `release_branch_prefix`. Unknown keys and the same repo listed twice are errors that name the entry.

### When the same repo turns up twice

Names are compared ignoring case.
1. A repo under `repositories` decides its own `dev_branch` and `security_workflow`.
2. `tags` are merged: its own first, then each source's, in file order.
3. `exclude` beats everything, including a listed repo.
4. Private repos found by a source are skipped; listed repos are always kept.

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

## License policy (Preferred, Not recommended, Restricted use)

List the licenses your team accepts under `licenses` in `config/repos.json`:

```json
"licenses": {
  "green":  ["MIT", "Apache-2.0", "BSD-*"],
  "yellow": ["MPL-2.0", "LGPL-*"],
  "red":    ["AGPL-*", "GPL-*", "SSPL-1.0"]
}
```

- Entries are SPDX ids or patterns (`*` matches anything), compared ignoring case. The same entry in two lists is a config error. If patterns overlap, the most restrictive class wins.
- Every repo license and dependency license gets a class: **Preferred** (`green`), **Not recommended** (`yellow`), **Restricted use** (`red`), or **unclassified** (on no list, or an expression that cannot be read). It is shown as a coloured dot, filterable as *License risk*, and the lists are printed under the dependency table.
- Expressions follow SPDX: `A OR B` takes the better class (you may choose), `A AND B` the worse, `AND` binds tighter than `OR`, parentheses are respected, and `A WITH exception` uses the exception if you listed it, else `A`. Several licenses reported together for one package (`MIT, Apache-2.0`) are treated as all applying, so the worst counts, because deps.dev does not say whether they are alternatives.
- Nothing is blocked or failed by this. It only colours and filters. An empty policy leaves everything *unclassified*.
- The names shown for the three lists can be changed with `licenses.labels` (see *Configuring the dependency scan*); the keys stay `green`, `yellow` and `red`.
- **No license.** `licenses.no_license` gives the class of a dependency or repository that nothing states a license for (the shipped config: `red`, as *Avoid* in the team's table). It applies only when every place that could state one was read: a registry and source repository with no license, a repository without a LICENSE file, an image none of the sources below give one for. A failed lookup, a check turned off and local actions are not counted as *no license*.

## Filters

Both pages share one filter component (`assets/filters.js`).

- Tick several values in a filter to see any of them (OR). Different filters combine (AND). A filter with nothing ticked is off.
- Each option shows how many results it would give with your other filters applied. An option that would give none is greyed out, so there are no dead ends.
- Active filters appear as chips; click one to remove it, or *Clear all*. Escape closes a dropdown.
- Filters live in the address bar (`?sec=failing&tag=DPG`), so a link shares the view. A link from the main page to `deps.html?repo=network-adapter&vuln=any` opens with that repository ticked and the vulnerability filter on.
- **Main page**: one bar filters every table at once (Repository, Tag, Security, Coverage, License risk, License, Vulnerabilities, Language). Security and Coverage follow the Development/Main switch. The release table has its own *Found as* and *Stability* filters and a *Show version* selector.
- **Dependency page**: Repository, Ecosystem, License, License risk, Vulnerabilities, Group, Update status, and a text search.
- Tests: `node --test tests/*.test.mjs` (also run in CI before the dashboard is built).

## Stack, dependencies and vulnerabilities

`scripts/collect_stack.py` writes `data/stack.json` on every refresh. The main page shows each repo's license, languages and technologies; `deps.html` lists every dependency each project names, on its development and its default branch.

**What is listed.** Every package a project names itself, in every group: `package.json` dependencies / dev / optional / peer; `pyproject.toml` `[project]` dependencies, optional-dependencies, `[dependency-groups]` (PEP 735), Poetry groups and `[build-system] requires`; `requirements*.txt`; direct `go.mod` requires and `tool` lines; Docker images from compose files and Dockerfiles; GitHub Actions; Terraform/OpenTofu providers; and tools that workflows install in their `run:` steps (`curl … install.sh | sh` from a GitHub repo such as Trivy, `pip`/`pipx`/`uv tool install`, `npm -g`, `npx`, `go install`). Indirect packages from lockfiles are not listed; lockfiles are read only for the exact version a range installs.

| Kind | Latest version | License | Vulnerabilities | Stars |
|---|---|---|---|---|
| npm, PyPI, Go | [deps.dev](https://deps.dev) | deps.dev, else the source repository's | [OSV.dev](https://osv.dev) at the installed version | deps.dev (source repository) |
| GitHub Actions | the action's latest release | the action repository's | GitHub Advisory Database, at the release a tag like `v4` points to today | deps.dev |
| Docker images | newest tag of the same shape in the registry (`17` → `18`); the version behind `latest` by digest | the first of: `dependencies.image_licenses`, the repository `dependencies.image_sources` names, the image's license label, the repository its source label names, its own program inside it (an OS or Go package named like the image) | [osv-scanner](https://github.com/google/osv-scanner) on the pulled image (OS packages and binaries inside it) | Docker Hub |
| Terraform providers | the provider registry | the `terraform-provider-<type>` repository's | none (no public database covers them) | deps.dev |
| Tools installed from a GitHub release | the latest release (what an unpinned install gets) | the repository's | OSV, when the tool is a Go module | deps.dev |

- **Every empty cell says why.** *N/A* means the value does not exist (a local action has no releases; an image that declares no license). *nil* means it exists but was not found, and the tooltip gives the reason, for example *Not published on PyPI*, *Registry lookup failed: 401 Unauthorized*, *Scan failed: docker pull failed*, *The tag is an unresolved ${VAR}*, or *dependencies.checks.images is turned off*.
- **Fixed in** is the one version that fixes every fixable advisory. For an image it is the count of fixable findings, since the fixes belong to packages inside the image; the card behind it lists every advisory with its package and fixed version.
- **`${VAR}` tags** are resolved from the repo's own compose defaults (`${VAR:-17}`) and `.env` example files.
- **Main stack only.** The Stack column lists the repo's real languages and frameworks. `stack` in `config/repos.json` controls it: `ignore_languages`, `ignore_techs`, `max_languages`, `max_techs`, `min_share`.
- **Development / Main.** One switch at the top of each page, above the filters, sets the branch for every table on it (coverage and security, stack, dependencies). Its buttons show how many repositories each lists. **Development lists only repositories whose development branch was found** (their `dev_branch`, or a branch matching `branches.development`); a repository without one is not shown there, and the note under the switch names it. Main lists every repository's default branch. The choice is remembered across the two pages and kept in the address bar (`?branch=main`).
- **Licenses with OR, AND and commas.** `A OR B` takes the better class, `A AND B` the worse; several licenses reported together (`MIT, Apache-2.0`) all apply, so the strictest counts.

**Safety.** Clones, manifests, workflow files, image names and registry answers all come from outside, so: the clone uses no token; child processes (git, npx, docker, osv-scanner) get an allowlisted environment without `GH_TOKEN`; files are read only if they are regular files under 1 MB; names are validated before they reach an API path or a command; registry calls go only to public hosts over HTTPS, with the connected address, every redirect, the response size (5 MB) and the time to receive it (60 s) checked; and log lines have control characters replaced.

## Configuring the dependency scan

**Every mapping and setting of the dependency scan lives in `config/dependencies.json`**, separate from `config/repos.json` (which says what to track and the license policy). Add an image's repository, state a license, class a new image or rename a group there; no code changes. Keys starting with `_` are notes and are ignored, so an entry can say why it was added:

```json
{
  "image_sources":  {"_note": "beckn-onix per its Docker Hub page", "fidedocker/onix-adapter": "beckn/beckn-onix"},
  "image_licenses": {"postgres": "PostgreSQL", "redis:7": "LicenseRef-RSALv2 OR SSPL-1.0"},
  "image_vendor_aliases": {"prom": "prometheus", "temporalio": "temporal"},
  "checks":         {"images": true},
  "images":         {"workers": 4, "scan_timeout": 900}
}
```

Every key is optional. A key left out keeps its built-in default, which is only switches and limits (everything on, nothing mapped); a list or map given replaces the built-in one. The shipped file holds all the current mappings. A mistake (unknown key, wrong type, number out of range) stops the refresh with an error that names the file and the key. A `"dependencies"` block in `repos.json` is an error that points here. The display names of the three license lists stay in `repos.json` under `licenses.labels`, next to the lists themselves.

| Key | What it does |
|---|---|
| `licenses.labels` | The names the dashboard shows for the green, yellow and red lists. |
| `checks.*` (dependencies.json) | Turn one kind of lookup off. Its cells then say it is turned off; `workflow_tools: false` stops listing CI tools at all. |
| `images.workers` | How many images are looked up at once (1–16). |
| `images.scan_timeout` | Seconds one image may take to pull and scan (60–3600). |
| `images.max_findings` | How many of an image's findings are kept for the card (the counts stay exact). |
| `images.resolve_limit` | How many version tags are compared by digest to find the version behind `latest`. |
| `images.max_tag_pages` | Pages of 1000 tags read per image; more is an error rather than a partial list. |
| `groups.aliases` | Group names read as another (`tests` → `test`), compared ignoring case. |
| `groups.workflow_purposes` | Group of a workflow-installed tool: the first key the workflow's file name contains. |
| `groups.by_ecosystem` | The group of every Docker image (`runtime`) and GitHub Action (`ci`). |
| `groups.default_workflow_group` | Group when no key matches. |
| `terraform.trusted_registries` | Registries whose providers take the license and stars of `<namespace>/terraform-provider-<type>`. |
| `license_aliases` | License texts in image labels and the SPDX id they mean. The defaults cover the usual spellings of Apache, MIT, BSD, GPL, AGPL and MPL; giving this key replaces them. |
| `ecosystem_names` | Names shown for each ecosystem, merged over the built-in ones: Node.js, Python, Go, GitHub Actions, Terraform, CLI tool, Container for (`npm`, `python`, `golang`, `docker`, `githubAction`, `terraform`, `githubRelease`). |
| `image_vendor_aliases` | An image's ecosystem is its vendor, read from its own name: an official Docker Hub image is itself (`redis`, `postgres`), any other is its namespace (`grafana/loki` → grafana, `docker.langfuse.com/langfuse/…` → langfuse, `cgr.dev/chainguard/minio` → chainguard, `ghcr.io/openagrinet/…` → openagrinet). Only names that read badly need an alias here (`prom` → prometheus, `temporalio` → temporal). |
| `image_sources` | An image's GitHub repository, written `owner/repo`, whose license is then looked up: `{"jaegertracing/all-in-one": "jaegertracing/jaeger"}`. Any spelling of the image matches (`postgres`, `docker.io/postgres`). |
| `image_licenses` | The license the team states for an image when nothing machine-readable gives one: `{"postgres": "PostgreSQL"}`. A key may carry a tag when the license depends on the version (`"redis:7"`, `"redis:alpine"`); `name:tag` is tried before `name`. It wins over every other source and applies even when the image cannot be pulled. |

An image named like its own repository (a `docker-compose.yml` with `build: .` and `image: <repo>`) is that repository built locally: it takes the repository's license and stars, and its latest version is N/A because it is never published.

A mistake (an unknown key, a wrong type, a number out of range) stops the refresh with an error that names it.

## Code layout

```
config/repos.json          what to track and how (see the sections above)
config/dependencies.json   every mapping and setting of the dependency scan (image sources and licenses, kinds, names, groups)
index.html, deps.html      the two pages (markup only)
assets/                    style.css and filters.js, tabs.js (shared); index.js, deps.js, deps.css (one page each)
data/                      coverage.json and stack.json, written by the workflow
scripts/
  aggregate_coverage.py    writes data/coverage.json
  collect_stack.py         writes data/stack.json
  repoconfig/              loads and validates config/repos.json, finds the repositories
  releasefind/             release branches, tags and release sets
  common/                  GitHub access, safe HTTPS to registries, versions, logging, child-process environment
  stackinfo/
    pipeline.py, record.py both branches of every repo; one repo's record
    sources/               what a repo declares: the analyser, manifests, workflow tools, ${VAR} tags, safe file reads
    lookups/               what other services say: deps.dev, OSV, Actions, registries, image scans, releases, Terraform, stars
    rules/                 what the dashboard concludes: license class, why a value is missing, the shown name
    settings.py            the dependencies block, applied for the run
tests/                     pytest for scripts/, node --test for assets/filters.js and assets/branches.js
```

## Refreshing

The workflow `.github/workflows/deploy.yml` runs once a day, on pushes to `main` that touch the dashboard, and on demand from **Actions → Refresh and deploy coverage dashboard → Run workflow**.

The coverage and security badges are loaded live by the browser, so they are always current. Only the line counts and run links wait for the next refresh.

## Secrets

| Secret | Needed for |
|---|---|
| `CODECOV_TOKEN` | Codecov API reads (public repos also work without it) |
| `DPG_QUERY_TOKEN` | **Needed for the default config.** A token that can read the organization's custom properties, used only for the `props.` repository search. Without it the refresh stops with an error (see *Choosing repositories*) |
| `DPG_PROJECT_TOKEN` | Optional. Only for a `project` source. Reads an org project board to discover repos. Classic token with `read:project`, or fine-grained with Organization → Projects: read |

The workflow's built-in `GITHUB_TOKEN` is enough for public repositories' branches, workflow runs and artifacts.

## Coverage fallback

If Codecov has nothing for the branch, the script looks for a coverage file in the artifacts of the latest successful run (of workflows named in `coverage.workflow_names`, default `CI`; `coverage.artifact_name_hints` limits which artifacts are read) on that branch. Supported: Cobertura/JaCoCo XML, LCOV, Istanbul `coverage-summary.json`, Go cover profiles.

## Local run

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
GH_TOKEN=<read-only token> python scripts/aggregate_coverage.py
GH_TOKEN=<read-only token> DPG_QUERY_TOKEN=<token> python scripts/collect_stack.py   # needs Node (npx), docker and osv-scanner for images (OSV_SCANNER=/path/to/osv-scanner)
python -m http.server 8000   # open http://localhost:8000
```
