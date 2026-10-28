"""Run specfy/stack-analyser on a shallow clone and reduce its output."""
import json, os, re, stat, subprocess, tempfile
import aggregate_coverage as ac
ANALYSER='@specfy/stack-analyser@1.27.6'
SAFE_ENV=('PATH','HOME','TMPDIR','TEMP','TMP','LANG','LC_ALL','XDG_CACHE_HOME','RUNNER_TEMP')

def child_env():
 """Environment for git and npx: an allowlist, so third-party npm code never sees GH_TOKEN, DPG_PROJECT_TOKEN or the Actions OIDC request token."""
 env={k:os.environ[k] for k in SAFE_ENV if k in os.environ}
 env.update(npm_config_ignore_scripts='true',GIT_TERMINAL_PROMPT='0')
 return env
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
  try:subprocess.run(['git','clone','-q','--depth','1','-b',branch,f'https://github.com/{ac.ORG}/{repo}.git',src],check=True,timeout=300,env=env,stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as e:raise RuntimeError(clone_error((e.stderr or b'').decode('utf-8','replace'),branch)) from None
  # the CLI joins -o onto the working directory, so pass a bare file name
  subprocess.run(['npx','--yes',ANALYSER,src,'--flat','-o','out.json'],cwd=tmp,check=True,timeout=600,stdout=subprocess.DEVNULL,env=env)
  with open(os.path.join(tmp,'out.json'),encoding='utf-8') as f:raw=json.load(f)
  raw['manifests']=read_manifests(src)   # groups and installed versions, read before the clone is removed
  return resolve_image_versions(raw,src)
SKIP_DIRS={'.git','node_modules','vendor','.venv'}
MAX_TEXT_BYTES=1_000_000
def _texts(src,want):
 """(path, text) of the files under src whose name passes want(name). Only regular files up to MAX_TEXT_BYTES are read:
 the clone is untrusted, and a symlink such as .env -> /proc/self/environ would otherwise put the runner's secrets into
 published versions (a FIFO or a huge file would hang the run). Unreadable files are skipped."""
 for root,dirs,files in os.walk(src):
  dirs[:]=[d for d in dirs if d not in SKIP_DIRS]
  for n in files:
   if not want(n):continue
   p=os.path.join(root,n)
   try:
    st=os.lstat(p)
    if not stat.S_ISREG(st.st_mode) or st.st_size>MAX_TEXT_BYTES:continue
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,encoding='utf-8',errors='replace') as f:yield p,f.read(MAX_TEXT_BYTES)
   except OSError:continue
def read_manifests(src):
 from .manifests import read
 return read(src)
def resolve_image_versions(raw,src):
 """stack-analyser keeps an image tag like ${POSTGRES_VERSION:-17} only up to the first colon. Replace such a tag with the value the
 repo itself gives: the compose default (${VAR:-17} or ${VAR-17}) on that image's line, else VAR=value from an .env example file.
 A tag no file defines is left as it is."""
 deps=raw.get('dependencies') or []
 todo=[d for d in deps if isinstance(d,list) and len(d)==3 and d[0]=='docker' and str(d[2]).startswith('${')]
 if not todo:return raw
 compose=list(_texts(src,lambda n:n.endswith(('.yml','.yaml')) or n.startswith('Dockerfile')))
 env={}
 for _,t in _texts(src,lambda n:n.startswith('.env') or n.endswith('.env.example')):
  for line in t.splitlines():
   m=re.match(r'\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*["\']?([^"\'\s#]+)',line)
   if m:env.setdefault(m.group(1),m.group(2))
 for d in todo:
  var=re.match(r'\$\{([A-Za-z_]\w*)',d[2])
  if not var:continue
  var=var.group(1);pat=re.compile(re.escape(d[1])+r':\$\{'+var+r':?-([^}\s]+)\}')
  found=next((m.group(1) for _,t in compose for m in [pat.search(t)] if m),None) or env.get(var)
  if found:d[2]=found
 return raw
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
