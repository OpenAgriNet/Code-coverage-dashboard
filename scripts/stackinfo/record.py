"""One repository's stack record: own license, analyser output, per-dependency license, vulnerabilities and license class."""
from common import github
from common.log import warn
from stackinfo.sources.analyser import analyse as run_analyser, summarize
from stackinfo.sources.manifests import attach as attach_groups, unlisted
from stackinfo.lookups.depsdev import dep_info
from stackinfo.lookups.osv import annotate
from stackinfo.lookups.actions import annotate as annotate_actions
from stackinfo.lookups.images import annotate as annotate_images
from stackinfo.lookups.terraform import annotate as annotate_terraform
from stackinfo.lookups.releases import annotate as annotate_releases
from stackinfo.lookups.stars import annotate as annotate_stars, github_stars, fill_licenses
from stackinfo.rules.policy import classify
from stackinfo.rules.reasons import explain
from stackinfo.rules.names import add_short

def repo_license(repo):
 """SPDX id of the repo's own LICENSE file, 'Other' if GitHub can't classify it, None if there is none."""
 lic=(github.api(f'/repos/{github.ORG}/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def repo_stars(repo):
 return github_stars(f'{github.ORG}/{repo}')
def stack_record(t,analyse=run_analyser,info=dep_info,vulns=annotate,actions=annotate_actions,images=annotate_images,stars=None,licenses=None,providers=None,tools=None,policy=None,stack=None):
 """Never raises: any failure becomes an `error` on the record, and the repo license is kept when it was read.
 `policy` is the green/yellow/red license lists; every license gets a license_class from it."""
 repo=t['name'];policy=policy or {}
 out={'repository':repo,'html_url':f'https://github.com/{github.ORG}/{repo}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':t.get('branch'),'branch_source':t.get('branch_source'),
  'stars':None,'license':None,'license_class':None,'languages':[],'techs':[],'dependencies':[],'error':None}
 try:out['stars']=repo_stars(repo)
 except Exception as e:warn(f'WARN stars {repo}: {e}')
 try:out['license']=repo_license(repo)
 except Exception as e:warn(f'WARN license {repo}: {e}')
 out['license_class']=classify(out['license'],policy)
 try:
  branch=out['branch']=t.get('branch') or github.default_branch(repo)
  raw=analyse(repo,branch);s=summarize(raw,stack);found=raw.get('manifests') or {}
  rows=s['dependencies']+unlisted(found,s['dependencies'])   # what the analyser misses: dependency-groups, build requires, CI tools
  out.update(languages=s['languages'],techs=s['techs'],dependencies=[info(*d) for d in rows])
  attach_groups(out['dependencies'],found);add_short(out['dependencies'])
  vulns(out['dependencies']);actions(out['dependencies']);images(out['dependencies']);(providers or annotate_terraform)(out['dependencies']);(tools or annotate_releases)(out['dependencies']);(stars or annotate_stars)(out['dependencies'])
  (licenses or fill_licenses)(out['dependencies'])
  for d in out['dependencies']:d['license_class']=classify(d.get('license'),policy)
  explain(out['dependencies'])   # every empty latest, license and vulns gets a reason
 except Exception as e:out['error']=str(e)[:180];warn(f'ERROR stack {repo}@{out["branch"]}: {e}')
 return out
