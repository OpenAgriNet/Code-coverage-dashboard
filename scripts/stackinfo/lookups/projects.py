"""Facts about a GitHub repository from deps.dev's project data: license and star count, at no cost to the workflow token's
GitHub API quota. One request per repository per run serves both. GitHub's own license detection is the fallback when
deps.dev cannot name a license ('non-standard', as for the MPL-2.0 HashiCorp providers)."""
from urllib.parse import quote
from common import github
from stackinfo.lookups.depsdev import D
PROJECTS={}
LICENSES={}

def project(repo):
 """deps.dev's record of github.com/<repo>, or None when it has none. Cached per run."""
 if repo not in PROJECTS:
  r=D.get(f'https://api.deps.dev/v3/projects/{quote("github.com/"+repo,safe="")}',timeout=30)
  if r.status_code==404:PROJECTS[repo]=None
  else:r.raise_for_status();PROJECTS[repo]=r.json()
 return PROJECTS[repo]
def project_stars(repo):
 """GitHub stars of owner/repo as deps.dev last saw them (refreshed daily)."""
 return (project(repo) or {}).get('starsCount')
def project_license(repo,api=None):
 """SPDX license of owner/repo: deps.dev's, else GitHub's own detection. Cached per run."""
 if repo in LICENSES:return LICENSES[repo]
 lic=(project(repo) or {}).get('license')
 if not lic or lic in ('non-standard','NOASSERTION'):
  got=((api or github.api)(f'/repos/{repo}/license') or {}).get('license') or {}
  lic=got.get('spdx_id') if got.get('spdx_id') not in (None,'NOASSERTION') else None
 LICENSES[repo]=lic
 return lic
