"""One repository's stack record: own license, analyser output, per-dependency license, vulnerabilities and license class."""
import sys
import aggregate_coverage as ac
from .analyser import analyse as run_analyser, summarize
from .depsdev import dep_info
from .vulns import annotate
from .actions import annotate as annotate_actions
from .policy import classify
from .manifests import attach as attach_groups

def repo_license(repo):
 """SPDX id of the repo's own LICENSE file, 'Other' if GitHub can't classify it, None if there is none."""
 lic=(ac.api(f'/repos/{ac.ORG}/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def stack_record(t,analyse=run_analyser,info=dep_info,vulns=annotate,actions=annotate_actions,policy=None,stack=None):
 """Never raises: any failure becomes an `error` on the record, and the repo license is kept when it was read.
 `policy` is the green/yellow/red license lists; every license gets a license_class from it."""
 repo=t['name'];policy=policy or {}
 out={'repository':repo,'html_url':f'https://github.com/{ac.ORG}/{repo}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':t.get('branch'),'branch_source':t.get('branch_source'),
  'license':None,'license_class':None,'languages':[],'techs':[],'dependencies':[],'error':None}
 try:out['license']=repo_license(repo)
 except Exception as e:print(f'WARN license {repo}: {e}',file=sys.stderr)
 out['license_class']=classify(out['license'],policy)
 try:
  branch=out['branch']=t.get('branch') or ac.default_branch(repo)
  raw=analyse(repo,branch);s=summarize(raw,stack)
  out.update(languages=s['languages'],techs=s['techs'],dependencies=[info(*d) for d in s['dependencies']])
  attach_groups(out['dependencies'],raw.get('manifests') or {})
  vulns(out['dependencies']);actions(out['dependencies'])
  for d in out['dependencies']:d['license_class']=classify(d.get('license'),policy)
 except Exception as e:out['error']=str(e)[:180];print(f'ERROR stack {repo}@{out["branch"]}: {e}',file=sys.stderr)
 return out
