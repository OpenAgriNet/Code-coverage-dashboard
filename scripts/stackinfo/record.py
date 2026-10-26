"""One repository's stack record: own license, analyser output, per-dependency license."""
import sys
import aggregate_coverage as ac
from .analyser import analyse as run_analyser, summarize
from .depsdev import dep_info

def repo_license(repo):
 """SPDX id of the repo's own LICENSE file, 'Other' if GitHub can't classify it, None if there is none."""
 lic=(ac.api(f'/repos/{ac.ORG}/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def stack_record(t,analyse=run_analyser,info=dep_info):
 """Never raises: an analyser failure becomes an `error` on the record, the repo license is kept."""
 repo=t['name'];branch=t.get('branch') or ac.default_branch(repo)
 out={'repository':repo,'html_url':f'https://github.com/{ac.ORG}/{repo}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':branch,
  'license':None,'languages':[],'techs':[],'dependencies':[],'error':None}
 try:out['license']=repo_license(repo)
 except Exception as e:print(f'WARN license {repo}: {e}',file=sys.stderr)
 try:
  s=summarize(analyse(repo,branch))
  out.update(languages=s['languages'],techs=s['techs'],dependencies=[info(*d) for d in s['dependencies']])
 except Exception as e:out['error']=str(e)[:180];print(f'ERROR stack {repo}@{branch}: {e}',file=sys.stderr)
 return out
