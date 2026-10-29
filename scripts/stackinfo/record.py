"""One repository's stack record: own license, analyser output, per-dependency license, vulnerabilities and license class."""
from common import github
from common.log import warn
from stackinfo import settings
from stackinfo.sources.analyser import analyse as run_analyser, summarize
from stackinfo.sources.manifests import attach as attach_groups, unlisted
from stackinfo.lookups.depsdev import dep_info
from stackinfo.lookups.osv import annotate
from stackinfo.lookups.actions import annotate as annotate_actions
from stackinfo.lookups.images import annotate as annotate_images
from stackinfo.lookups.terraform import annotate as annotate_terraform
from stackinfo.lookups.releases import annotate as annotate_releases
from stackinfo.lookups.stars import annotate as annotate_stars, github_stars, fill_licenses
from stackinfo.lookups.repostate import annotate as annotate_repo_state
from stackinfo.rules.policy import classify
from stackinfo.rules.reasons import explain
from stackinfo.rules.names import add_short
from stackinfo.rules.kinds import add_kinds

def repo_license(repo):
 """SPDX id of the repo's own LICENSE file, 'Other' if GitHub can't classify it, None if there is none."""
 lic=(github.api(f'/repos/{github.ORG}/{repo}/license') or {}).get('license')
 if not lic:return None
 return lic.get('spdx_id') if lic.get('spdx_id') not in (None,'NOASSERTION') else 'Other'
def repo_stars(repo):
 return github_stars(f'{github.ORG}/{repo}')
def stack_record(t,analyse=run_analyser,info=dep_info,vulns=annotate,actions=annotate_actions,images=annotate_images,stars=None,licenses=None,repo_state=None,providers=None,tools=None,policy=None,stack=None):
 """Never raises: any failure becomes an `error` on the record, and the repo license is kept when it was read.
 `policy` is the green/yellow/red license lists; every license gets a license_class from it."""
 repo=t['name'];policy=policy or {}
 out={'repository':repo,'html_url':f'https://github.com/{github.ORG}/{repo}','dpg':'DPG' in t.get('tags',[]),'tags':t.get('tags',[]),'branch':t.get('branch'),'branch_source':t.get('branch_source'),
  'stars':None,'license':None,'license_class':None,'languages':[],'techs':[],'dependencies':[],'error':None}
 try:out['stars']=repo_stars(repo)
 except Exception as e:warn(f'WARN stars {repo}: {e}')
 looked=False
 try:out['license']=repo_license(repo);looked=True
 except Exception as e:warn(f'WARN license {repo}: {e}')
 # a repository GitHub finds no LICENSE file in has no license: the policy's no_license class (a failed lookup is not that)
 out['license_class']=classify(out['license'],policy) if out['license'] or not looked else policy.get('no_license')
 try:
  branch=out['branch']=t.get('branch') or github.default_branch(repo)
  raw=analyse(repo,branch);s=summarize(raw,stack);found=raw.get('manifests') or {}
  rows=s['dependencies']+unlisted(found,s['dependencies'])   # what the analyser misses: dependency-groups, build requires, CI tools
  out.update(languages=s['languages'],techs=s['techs'],dependencies=[info(*d) for d in rows])
  attach_groups(out['dependencies'],found);add_short(out['dependencies']);add_kinds(out['dependencies'])
  deps=out['dependencies']
  # each lookup can be turned off under dependencies.checks; explain() then says so in the empty cells
  if settings.check('vulnerabilities'):vulns(deps)
  if settings.check('actions'):actions(deps)
  if settings.check('images'):images(deps)
  # an image named like this repository is the repository itself, built from its Dockerfile (docker-compose build: .) and not
  # published: it takes the repository's license and stars, and explain() says why it has no versions or scan
  for d in deps:
   if d.get('ecosystem')=='docker' and d.get('name','').lower() in (repo.lower(),f'{github.ORG}/{repo}'.lower()):
    d['own']=True;d['project']=f'github.com/{github.ORG}/{repo}'
    if not d.get('license') and out['license']:d.update(license=out['license'],license_of='repository')
   # an action stored in this repository (./.github/actions/x) is this repository's code, under its license
   if d.get('ecosystem')=='githubAction' and d.get('name','').startswith('./') and out['license'] and not d.get('license'):
    d.update(license=out['license'],license_of='repository')
  if settings.check('terraform'):(providers or annotate_terraform)(deps)
  (tools or annotate_releases)(deps)   # rows exist only when dependencies.checks.workflow_tools listed them
  if settings.check('stars'):(stars or annotate_stars)(deps)
  (repo_state or annotate_repo_state)(deps)   # archived source repositories; guessed ones that do not exist
  (licenses or fill_licenses)(out['dependencies'])
  for d in out['dependencies']:d['license_class']=classify(d.get('license'),policy)
  explain(out['dependencies'])   # every empty latest, license and vulns gets a reason
  for d in out['dependencies']:
   if ((d.get('missing') or {}).get('license') or {}).get('kind')=='none':d['license_class']=policy.get('no_license')   # nothing states a license
 except Exception as e:out['error']=str(e)[:180];warn(f'ERROR stack {repo}@{out["branch"]}: {e}')
 return out
