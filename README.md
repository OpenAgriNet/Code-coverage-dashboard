<<<<<<< HEAD
# Code-coverage-dashboard
Centralized GitHub Pages dashboard for monitoring code coverage across DPG repositories, automatically updated using existing GitHub Actions coverage reports.
=======
# OpenAgriNet Code Coverage Dashboard

A static GitHub Pages dashboard that reads existing GitHub Actions artifacts. It does not checkout application repositories, install their dependencies, or rerun tests.

## Setup

1. Create `OpenAgriNet/coverage-dashboard` and copy these files to its `main` branch.
2. Edit `config/repos.json` to list every repository you want to track. The included names are only a starter based on the screenshot.
3. Create a fine-grained personal access token with **Actions: read** and **Metadata: read** on the selected repositories. It must have access to private repositories too, and may require organization approval.
4. In the dashboard repo, go to **Settings → Secrets and variables → Actions** and add repository secret `COVERAGE_READ_TOKEN` with that token.
5. Go to **Settings → Pages** and select **GitHub Actions** as the deployment source.
6. Run **Actions → Refresh and deploy coverage dashboard → Run workflow**. Open the Pages URL from the workflow summary. Refreshes run every six hours.

## Supported artifact reports

Cobertura-style XML (`coverage.xml`, `cobertura.xml`), JaCoCo XML (`jacoco.xml`), LCOV (`lcov.info`), Istanbul coverage summary JSON (`coverage-summary.json`), and basic Go cover profiles. The script checks artifacts attached to the latest completed successful run (falling back to the latest completed run).

GitHub Actions job summaries are not a standardized machine-readable coverage API. If a repo only prints a percentage in `$GITHUB_STEP_SUMMARY`, this starter cannot reliably extract it. For that repository, adapt the parser or add a small JSON artifact to its existing workflow; this does not require rerunning tests. Expired or absent artifacts will show as missing, not 0%.

## Local test

```bash
python -m pip install requests
GH_TOKEN=YOUR_TOKEN GITHUB_ORG=OpenAgriNet python scripts/aggregate_coverage.py
python -m http.server 8000
```
Open `http://localhost:8000`.
>>>>>>> 327392c (Add coverage dashboard, aggregator script and deploy workflow)
