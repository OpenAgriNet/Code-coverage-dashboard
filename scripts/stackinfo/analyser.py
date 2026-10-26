"""Run specfy/stack-analyser on a shallow clone and reduce its output."""
import json, os, subprocess, tempfile
import aggregate_coverage as ac
ANALYSER='@specfy/stack-analyser@1.27.6'
SAFE_ENV=('PATH','HOME','TMPDIR','TEMP','TMP','LANG','LC_ALL','XDG_CACHE_HOME','RUNNER_TEMP')

def child_env():
 """Environment for git and npx: an allowlist, so third-party npm code never sees GH_TOKEN, DPG_PROJECT_TOKEN or the Actions OIDC request token."""
 env={k:os.environ[k] for k in SAFE_ENV if k in os.environ}
 env.update(npm_config_ignore_scripts='true',GIT_TERMINAL_PROMPT='0')
 return env
def analyse(repo,branch):
 """Raw stack-analyser output (flat) for a shallow clone of repo@branch."""
 env=child_env()
 with tempfile.TemporaryDirectory() as tmp:
  src=os.path.join(tmp,'src')
  subprocess.run(['git','clone','-q','--depth','1','-b',branch,f'https://github.com/{ac.ORG}/{repo}.git',src],check=True,timeout=300,env=env)
  # the CLI joins -o onto the working directory, so pass a bare file name
  subprocess.run(['npx','--yes',ANALYSER,src,'--flat','-o','out.json'],cwd=tmp,check=True,timeout=600,stdout=subprocess.DEVNULL,env=env)
  with open(os.path.join(tmp,'out.json'),encoding='utf-8') as f:return json.load(f)
def main_stack(langs,techs,stack):
 """Only the main stack: drop markup, data and tooling (stack['ignore_*'], compared ignoring case), then keep languages that are
 at least min_share of the remaining files (stack-analyser labels a stray go.mod as AMPL) and at most max_languages of them."""
 skip_l={x.lower() for x in stack['ignore_languages']};skip_t={x.lower() for x in stack['ignore_techs']}
 code=[l for l in langs if l[0].lower() not in skip_l];total=sum(n for _,n in code)
 return ([l for l in code if total and l[1]/total>=stack['min_share']][:stack['max_languages']],[t for t in techs if t.lower() not in skip_t][:stack['max_techs']])
def summarize(raw,stack=None):
 """Languages by file count, tech keys, and deduplicated [ecosystem, name, version] dependencies.
 With `stack` (the config's stack settings) languages and techs are cut down to the main stack."""
 langs=sorted((raw.get('languages') or {}).items(),key=lambda x:(-x[1],x[0]))
 seen=set();deps=[]
 for dep in raw.get('dependencies') or []:
  if not isinstance(dep,(list,tuple)) or len(dep)!=3:continue  # one odd manifest entry must not lose the whole repo
  key=tuple(dep)
  if key in seen:continue
  seen.add(key);deps.append(list(key))
 techs=sorted(set(raw.get('techs') or []))
 if stack:langs,techs=main_stack(langs,techs,stack)
 return {'languages':langs,'techs':techs,'dependencies':sorted(deps,key=lambda d:(d[0],d[1].lower()))}
