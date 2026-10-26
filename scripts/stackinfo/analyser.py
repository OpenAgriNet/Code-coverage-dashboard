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
def summarize(raw):
 """Languages by file count, tech keys, and deduplicated [ecosystem, name, version] dependencies."""
 langs=sorted((raw.get('languages') or {}).items(),key=lambda x:(-x[1],x[0]))
 seen=set();deps=[]
 for dep in raw.get('dependencies') or []:
  if not isinstance(dep,(list,tuple)) or len(dep)!=3:continue  # one odd manifest entry must not lose the whole repo
  key=tuple(dep)
  if key in seen:continue
  seen.add(key);deps.append(list(key))
 return {'languages':langs,'techs':sorted(set(raw.get('techs') or [])),'dependencies':sorted(deps,key=lambda d:(d[0],d[1].lower()))}
