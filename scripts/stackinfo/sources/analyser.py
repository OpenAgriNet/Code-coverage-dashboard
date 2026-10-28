"""Run specfy/stack-analyser on a shallow clone and reduce its output."""
import json, os, subprocess, tempfile
from common.github import ORG
from common.proc import child_env
from stackinfo.sources.composevars import resolve_image_versions
ANALYSER='@specfy/stack-analyser@1.27.6'
def clone_error(stderr,branch):
 """A readable reason for a failed git clone."""
 if 'could not read Username' in stderr or 'Authentication failed' in stderr:return 'private repository: not analysed (the analyser clones without a token, so no secret reaches third-party code)'
 if 'Remote branch' in stderr and 'not found' in stderr:return f'branch {branch} does not exist (an empty repository has no branches)'
 last=stderr.strip().splitlines()[-1] if stderr.strip() else 'git failed'
 return f'could not clone: {last[:150]}'
def analyse(repo,branch):
 """Raw stack-analyser output (flat) for a shallow clone of repo@branch."""
 env=child_env()
 with tempfile.TemporaryDirectory() as tmp:
  src=os.path.join(tmp,'src')
  try:subprocess.run(['git','clone','-q','--depth','1','-b',branch,f'https://github.com/{ORG}/{repo}.git',src],check=True,timeout=300,env=env,stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as e:raise RuntimeError(clone_error((e.stderr or b'').decode('utf-8','replace'),branch)) from None
  # the CLI joins -o onto the working directory, so pass a bare file name
  subprocess.run(['npx','--yes',ANALYSER,src,'--flat','-o','out.json'],cwd=tmp,check=True,timeout=600,stdout=subprocess.DEVNULL,env=env)
  with open(os.path.join(tmp,'out.json'),encoding='utf-8') as f:raw=json.load(f)
  raw['manifests']=read_manifests(src)   # groups and installed versions, read before the clone is removed
  return resolve_image_versions(raw,src)
def read_manifests(src):
 """Packages the manifests declare, plus tools the workflows install, keyed (ecosystem, name)."""
 from stackinfo.sources.manifests import read
 from stackinfo.sources.tools import read as read_tools, merge
 return merge(read(src),read_tools(src))
def main_stack(langs,techs,stack):
 """Only the main stack: drop markup, data and tooling (stack['ignore_*'], compared ignoring case), then keep languages that are
 at least min_share of the remaining files (stack-analyser labels a stray go.mod as AMPL) and at most max_languages of them."""
 skip_l={x.lower() for x in stack['ignore_languages']};skip_t={x.lower() for x in stack['ignore_techs']}
 code=[l for l in langs if l[0].lower() not in skip_l];total=sum(n for _,n in code)
 return ([l for l in code if total and l[1]/total>=stack['min_share']][:stack['max_languages']],[t for t in techs if t.lower() not in skip_t][:stack['max_techs']])
NOT_DEPENDENCIES={'terraform.resource'}   # resource types in .tf files (aws_s3_bucket), not packages
def summarize(raw,stack=None):
 """Languages by file count, tech keys, and deduplicated [ecosystem, name, version] dependencies.
 With `stack` (the config's stack settings) languages and techs are cut down to the main stack."""
 langs=sorted((raw.get('languages') or {}).items(),key=lambda x:(-x[1],x[0]))
 seen=set();deps=[]
 for dep in raw.get('dependencies') or []:
  if not isinstance(dep,(list,tuple)) or len(dep)!=3:continue  # one odd manifest entry must not lose the whole repo
  if dep[0] in NOT_DEPENDENCIES:continue
  key=tuple(dep)
  if key in seen:continue
  seen.add(key);deps.append(list(key))
 techs=sorted(set(raw.get('techs') or []))
 if stack:langs,techs=main_stack(langs,techs,stack)
 return {'languages':langs,'techs':techs,'dependencies':sorted(deps,key=lambda d:(d[0],d[1].lower()))}
