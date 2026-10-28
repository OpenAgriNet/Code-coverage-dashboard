"""Popularity: GitHub stars of the repository each dependency comes from, and Docker Hub stars of Docker Hub images.
Actions and Go modules on github.com name their repository; npm and PyPI packages get it from deps.dev's source-repo link.
Dependency stars come from deps.dev's project data, so they cost none of the workflow token's GitHub API quota; only the
tracked repos' own stars are asked of GitHub."""
import re
from urllib.parse import quote
from common import github
from common.log import warn
from common.safehttp import get as safe_get
from stackinfo.lookups.actions import NAME, repo_of
from stackinfo.lookups import registry
from stackinfo.lookups.depsdev import D
from stackinfo import settings
from stackinfo.lookups.projects import project_stars, project_license
from stackinfo.rules.reasons import short_error
GH=re.compile(r'github\.com/([^/]+/[^/]+)')
CACHE={}

def _ok(repo):
 return bool(repo) and bool(NAME.fullmatch(repo)) and '..' not in repo
def _project(d):
 m=GH.fullmatch(d.get('project') or '')
 return m.group(1) if m and not m.group(1).startswith('sponsors/') else None
GOPKG=re.compile(r'gopkg\.in/(?:([A-Za-z0-9_-]+)/)?([A-Za-z0-9_.-]+?)\.v\d+(?:/.*)?')
def go_vanity(name):
 """The GitHub repository of a Go module path that names none, by the hosts' own rules: golang.org/x/<name> is mirrored at
 github.com/golang/<name>; gopkg.in/<name>.vN is github.com/go-<name>/<name>, gopkg.in/<user>/<name>.vN github.com/<user>/<name>."""
 p=name.split('/')
 if len(p)>=3 and p[0]=='golang.org' and p[1]=='x':return f'golang/{p[2]}'
 m=GOPKG.fullmatch(name)
 if m:return f'{m.group(1)}/{m.group(2)}' if m.group(1) else f'go-{m.group(2)}/{m.group(2)}'
 return None
def source_repo(d):
 """'owner/repo' on GitHub the dependency is developed in, or None."""
 eco,name=d.get('ecosystem'),d.get('name','')
 if eco=='githubAction':repo=None if name.startswith(('./','docker://')) else repo_of(name)
 elif eco=='golang':
  m=GH.match(name)
  repo=m.group(1) if m else _project(d) or go_vanity(name)   # deps.dev knows go.opentelemetry.io/otel's repository
 else:repo=_project(d)
 return repo if _ok(repo) else None
def _count(v):
 """A star count is a whole number of 0 or more; anything else an API sends back is dropped, so the page never prints it."""
 return v if isinstance(v,int) and not isinstance(v,bool) and v>=0 else None
def github_stars(repo,api=github.api):
 return (api(f'/repos/{repo}') or {}).get('stargazers_count')
def hub_stars(name,get=None):
 """Star count of a Docker Hub image; None for images on other registries."""
 host,path=registry.split(name)
 if host!='registry-1.docker.io':return None
 r=(get or safe_get)(f'https://hub.docker.com/v2/repositories/{path}/')
 return r.json().get('star_count') if r.status_code==200 else None
def pypi_license(name,get=None):
 """License PyPI's own metadata states for a package: its SPDX license_expression, else its license text or license
 classifier when config/dependencies.json license_aliases names the SPDX id it means. None when none does."""
 r=(get or D.get)(f'https://pypi.org/pypi/{quote(name,safe="")}/json',timeout=30)
 if r.status_code==404:return None
 r.raise_for_status()
 i=r.json().get('info') or {}
 if i.get('license_expression'):return i['license_expression']
 aliases=settings.get('license_aliases')
 for t in [i.get('license') or '']+[c.split(' :: ')[-1] for c in i.get('classifiers') or [] if c.startswith('License ::')]:
  if t.strip().lower() in aliases:return aliases[t.strip().lower()]
 return None

def fill_licenses(deps,license_of=None,pypi=None):
 """A package whose registry states no license takes its source repository's license (license_of 'source'), e.g. a Go
 submodule deps.dev has no license for. A package deps.dev calls 'non-standard' (it could not match the license text to an SPDX
 id) gets a second opinion: its source repository's license as deps.dev or GitHub's own detection names it (license_of
 'github'; huggingface-hub Apache-2.0, tiktoken MIT), then for a Python package PyPI's own metadata (license_of 'pypi';
 pypdf BSD-3-Clause). When none can name it, it stays 'non-standard'. A failed lookup leaves the license as it was."""
 license_of=license_of or project_license
 pypi=pypi or pypi_license
 for d in deps:
  nonstd=d.get('license')=='non-standard'
  if (d.get('license') and not nonstd) or d.get('license_of')=='error' or d.get('ecosystem') not in ('npm','python','golang','terraform','githubRelease'):continue
  repo=source_repo(d)
  if not repo:continue
  try:lic=license_of(repo)
  except Exception as e:
   if not nonstd:d.setdefault('errors',{})['license']=f'deps.dev: {short_error(e)}'   # not a missing license
   continue
  if lic and lic!='non-standard':d.update(license=lic,license_of='github' if nonstd else 'source');continue
  if nonstd and d.get('ecosystem')=='python':
   try:lic=pypi(d['name'])
   except Exception:continue
   if lic:d.update(license=lic,license_of='pypi')
def annotate(deps,api=project_stars,hub=hub_stars,cache=CACHE,log=warn):
 """Add stars and stars_of (where they were counted) to every dependency that has a known home. A failed lookup adds nothing."""
 for d in deps:
  if d.get('ecosystem')=='docker' and not source_repo(d):   # no GitHub repository known: Docker Hub's own stars
   if not registry.NAME.fullmatch(d['name']) or registry.split(d['name'])[0]!='registry-1.docker.io':continue
   key=('hub',registry.split(d['name'])[1]);where='hub.docker.com/'+key[1].replace('library/','_/',1);fetch=lambda:hub(d['name'])
  else:
   repo=source_repo(d)
   if not repo:continue
   key=('github',repo);where='github.com/'+repo;fetch=lambda:api(repo)
  if key not in cache:
   try:cache[key]=_count(fetch())
   except Exception as e:cache[key]=None;log(f'WARN stars lookup failed for {where}: {e}')
  if cache[key] is not None:d.update(stars=cache[key],stars_of=where)
