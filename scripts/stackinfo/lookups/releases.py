"""Tools installed from a GitHub release (curl ... install.sh | sh), such as Trivy: latest release, the release an unpinned
install gets today, and, when the tool is also a Go module (most release-installed CLIs are), its known vulnerabilities
from OSV at that release."""
from urllib.parse import quote
from common import github
from common.log import warn
from stackinfo.lookups.actions import NAME, latest as latest_release
from stackinfo.lookups.depsdev import fetch as depsdev_fetch
from stackinfo.lookups.osv import annotate as osv_annotate
from stackinfo.rules.reasons import short_error
CACHE={}

def lookup(repo,version,api,is_go,check):
 out={'latest':latest_release(repo,api),'project':f'github.com/{repo}'}
 at=out['latest'] if version in ('latest','',None) else version
 if at and at!=version:out['resolved']=at
 mod=f'github.com/{repo}'
 if at and is_go(mod):
  probe=[{'ecosystem':'golang','name':mod,'version':at}];check(probe)
  out['vulns']=probe[0]['vulns']
  if probe[0].get('errors'):out['errors']=probe[0]['errors']
 return out
def is_go_module(mod):
 return depsdev_fetch(f'GO/packages/{quote(mod,safe="")}') is not None
def annotate(deps,api=github.api,is_go=is_go_module,check=osv_annotate,cache=CACHE,log=warn):
 for d in deps:
  if d.get('ecosystem')!='githubRelease':continue
  repo,ver=d['name'],str(d.get('version') or 'latest')
  if not NAME.fullmatch(repo) or '..' in repo:log(f'WARN release tool not checked: {repo}');continue
  k=(repo,ver)
  if k not in cache:
   try:cache[k]=lookup(repo,ver,api,is_go,check)
   except Exception as e:m=f'GitHub: {short_error(e)}';cache[k]={'errors':{'latest':m,'vulns':m}};log(f'WARN release tool {repo}: {e}')
  d.update({x:(dict(v) if isinstance(v,dict) else v) for x,v in cache[k].items()})
  d.setdefault('vulns',None)
