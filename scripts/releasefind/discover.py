"""Collect release versions of one repo from every enabled source and merge them into one list."""
import sys
from .versions import parse
PAGE=100; TAG_PAGES=3

def branches(org,repo,rcfg,get):
 return [(r['ref'][len('refs/heads/'):],r['object']['sha'],None) for r in get(f'/repos/{org}/{repo}/git/matching-refs/heads/{rcfg["branch_prefix"]}') or []]
def tags(org,repo,get):
 out=[]
 for page in range(1,TAG_PAGES+1):
  items=get(f'/repos/{org}/{repo}/tags?per_page={PAGE}&page={page}') or []
  out+=[(t['name'],t['commit']['sha'],None) for t in items]
  if len(items)<PAGE:break
 return out
def release_list(org,repo,get):
 """(tag_name, None, {'prerelease','published_at'}) for published GitHub Releases; the sha is filled in from the tag list."""
 return [(r['tag_name'],None,{'prerelease':bool(r.get('prerelease')),'published_at':r.get('published_at')}) for r in get(f'/repos/{org}/{repo}/releases?per_page={PAGE}') or [] if not r.get('draft')]
def find_versions(org,repo,rcfg,get,log=lambda m:print(m,file=sys.stderr)):
 """{'versions': newest first, at most max_versions, 'total': count before the cap}.
 Each version: version, ref, ref_kind ('branch' or 'tag'), sha, kinds (every source that has it), prerelease, published_at.
 The ref and sha come from the first source in rcfg['sources'] that has the version."""
 found={};tag_sha={};wanted=rcfg['sources']
 fetch={'branch':lambda:branches(org,repo,rcfg,get),'tag':lambda:tags(org,repo,get),'release':lambda:release_list(org,repo,get)}
 if 'release' in wanted and 'tag' not in wanted:fetch['tag']=lambda:tags(org,repo,get)  # only to resolve release shas
 data={}
 for kind in dict.fromkeys(wanted+(['tag'] if 'release' in wanted else [])):
  try:data[kind]=fetch[kind]()
  except Exception as e:log(f'WARN {repo}: {kind} lookup failed: {e}');data[kind]=[]
 tag_sha={n:s for n,s,_ in data.get('tag',[])}
 for kind in wanted:
  for name,sha,extra in data.get(kind,[]):
   p=parse(kind,name,rcfg)
   if not p:continue
   sha=sha or tag_sha.get(name)
   if not sha:log(f'WARN {repo}: release {name} has no matching tag; skipped');continue
   v=found.setdefault(p['identity'],{'version':p['version'],'ref':name,'ref_kind':'branch' if kind=='branch' else 'tag','sha':sha,'kinds':[],'prerelease':False,'published_at':None,'sort':p['sort']})
   v['kinds'].append(kind);v['prerelease']|=bool(p['pre'] or (extra or {}).get('prerelease'));v['published_at']=v['published_at'] or (extra or {}).get('published_at')
 vs=sorted(found.values(),key=lambda v:v['sort'],reverse=True)
 if not rcfg['include_prereleases']:vs=[v for v in vs if not v['prerelease']]
 return {'versions':[{k:v for k,v in x.items() if k!='sort'} for x in vs[:rcfg['max_versions']]],'total':len(vs)}
