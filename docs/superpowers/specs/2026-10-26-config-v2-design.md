# Config v2: find, don't list

## Intent
`config/repos.json` had grown into a place where the team re-typed what the scripts already know: every repo with its branch, a fixed fallback list of repo names, a project-board id nobody uses, and loose top-level settings (`defaults`, `workflow_names`, `artifact_name_hints`). The dashboard already has a Development/Main switch, so a per-repo `branch` also contradicted it. The file should say only what the scripts cannot know.

## Goals
- Repos come from `sources` (a GitHub search query) minus `exclude`. `repositories` holds only custom additions or per-repo overrides.
- No `branch` anywhere. **Main** is the repo's default branch. **Development** is the repo's `dev_branch` if given, else the first branch matching `branches.development` (a regex set once), else the default branch, labelled as such in the UI.
- Named release sets: `release_sets` maps an alias (`v1`, `v2`) to each repo's own tag, so repos that version themselves differently can be shown as one release. The set marked `"current": true` is the current one; if none is marked, the last one listed. The dashboard can filter by alias.
- Related settings are grouped: `coverage`, `security`, `stack`, `licenses`, `releases`.
- Typos and removed keys are errors that say what to use instead.

## Non-goals
- No change to how releases are discovered (`releases` block) or measured.
- No automatic detection of which tag belongs to which set.
- No per-repo `branch` override (use `dev_branch`; Main is always the default branch).

## Decisions (the user's, as given)
- Aliases and tags are written by the user in the config.
- If no development branch matches, the Development view shows the default branch, labelled "default".
- `fallback` lists go away. A source that fails stops the refresh with a visible error, so the dashboard keeps its last good data instead of shrinking silently. A query that matches nothing is only a warning.
- The project-board example (#9) leaves the default config; the source type stays supported.

## Builder's calls (mine, to be reviewed)
- `current` defaults to the last listed set; the dashboard opens on the current set.
- If several branches match the development regex, the first alphabetically wins and the choice is logged.
- A tag in a release set that discovery did not find (too old for `max_versions`, or not matching `tag_pattern`) shows "tag not found" rather than being measured on the side.
- Unknown keys in any block are errors, not ignored.
- `exclude` in the shipped config: `engineering-tracker` and `Code-coverage-dashboard`. Spec-only repos (`network-specs`, `protocol-specifications-v2`) stay until the team says otherwise.
- `infra-automation` stays under `repositories` as a custom addition: it is private, and sources skip private repos on a public dashboard.
