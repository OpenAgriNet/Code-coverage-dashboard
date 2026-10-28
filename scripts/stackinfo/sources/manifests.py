"""Which group each dependency a project names is declared in (main, dev, test, security, optional...), and the exact version its
lockfile installs. Only packages the project names itself; indirect packages in lockfiles are never listed."""
import json, os, re, tomllib
from common.versions import is_exact, normal
SPELLING={'tests':'test','testing':'test','develop':'dev','development':'dev'}
NPM={'dependencies':'main','devDependencies':'dev','optionalDependencies':'optional','peerDependencies':'peer'}
BY_ECOSYSTEM={'docker':'runtime','githubAction':'ci'}
REQ=re.compile(r'requirements(?:[-_](?P<a>[\w.-]+))?\.txt|(?P<b>[\w.-]+)\.txt')
PEP508=re.compile(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)')

def group_name(g):
 g=str(g).strip().lower();return SPELLING.get(g,g)
def key(eco,name):
 return (eco,normal(name) if eco=='python' else name)
def add_entry(out,eco,name,group,source,declared=None):
 e=out.setdefault(key(eco,name),{'name':name,'groups':set(),'installed':None,'sources':set(),'declared':None})
 e['groups'].add(group_name(group));e['sources'].add(source)
 if declared and not e['declared']:e['declared']=str(declared).strip()
def pep508_name(spec):
 m=PEP508.match(spec) if isinstance(spec,str) else None
 return m.group(1) if m else None
def pep508_version(spec):
 """The version part of 'pytest[extra]>=9.1.1 ; python_version>"3"' -> '>=9.1.1'."""
 rest=PEP508.sub('',spec.split(';',1)[0],count=1).strip()
 return re.sub(r'^\[[^\]]*\]','',rest).strip() or None
def _npm(out,rel,text):
 d=json.loads(text)
 for field,group in NPM.items():
  for name,spec in (d.get(field) or {}).items():add_entry(out,'npm',name,group,rel,spec if isinstance(spec,str) else None)
def _pyproject(out,rel,text):
 d=tomllib.loads(text);proj=d.get('project') or {};poetry=(d.get('tool') or {}).get('poetry') or {}
 sets=[('main',proj.get('dependencies') or [])]
 sets+=[(g,v) for g,v in (proj.get('optional-dependencies') or {}).items()]
 sets+=[(g,v) for g,v in (d.get('dependency-groups') or {}).items()]   # PEP 735; {include-group=...} entries are not packages
 sets+=[('build',(d.get('build-system') or {}).get('requires') or [])]
 for g,specs in sets:
  for s in specs:
   n=pep508_name(s)
   if n:add_entry(out,'python',n,g,rel,pep508_version(s))
 for g,deps in [('main',poetry.get('dependencies') or {}),('dev',poetry.get('dev-dependencies') or {})]+[(g,(v or {}).get('dependencies') or {}) for g,v in (poetry.get('group') or {}).items()]:
  for n,spec in deps.items():
   if n.lower()!='python':add_entry(out,'python',n,g,rel,spec if isinstance(spec,str) else (spec or {}).get('version') if isinstance(spec,dict) else None)
def _requirements(out,rel,text):
 parts=rel.split('/');m=REQ.fullmatch(parts[-1])
 g=m.group('a') if m.group('a') else m.group('b') if len(parts)>1 and parts[-2]=='requirements' else None
 g='main' if g in (None,'base','common','requirements') else g
 for line in text.splitlines():
  line=line.split('#',1)[0].strip()
  if not line or line.startswith('-'):continue
  n=pep508_name(line)
  if n:add_entry(out,'python',n,g,rel,pep508_version(line))
def _gomod(out,rel,text):
 block=False
 for line in text.splitlines():
  s=line.strip()
  if s.startswith('require ('):block=True;continue
  if block and s==')':block=False;continue
  if '// indirect' in s:continue
  if s.startswith('tool ') and len(s.split())==2:add_entry(out,'golang',s.split()[1],'tool',rel);continue
  body=s[len('require '):] if s.startswith('require ') and not s.endswith('(') else s if block else None
  if body and len(body.split())>=2:add_entry(out,'golang',body.split()[0],'main',rel,body.split()[1])
def _locks(rel,text,name):
 """{(ecosystem, name): version} of the packages a lockfile installs at top level."""
 if name=='package-lock.json':
  pk=json.loads(text).get('packages') or {}
  return {('npm',p[len('node_modules/'):]):v.get('version') for p,v in pk.items() if p.startswith('node_modules/') and '/node_modules/' not in p and v.get('version')}
 return {key('python',p.get('name','')):p.get('version') for p in tomllib.loads(text).get('package') or [] if p.get('name') and p.get('version')}
READERS={'package.json':_npm,'pyproject.toml':_pyproject,'go.mod':_gomod}
LOCKS=('package-lock.json','uv.lock','poetry.lock')
def wanted(n):
 return n in READERS or n in LOCKS or n.endswith('.txt')
def read(src,texts=None):
 """{(ecosystem, name): {'groups': [...], 'installed': version or None, 'sources': [manifest paths]}} for every dependency a manifest
 under src names. Unparseable files are skipped. installed comes from a lockfile in the manifest's own directory."""
 if texts is None:
  from stackinfo.sources.files import texts as read_texts   # regular, size-capped files only
  texts=read_texts
 out={};locks={}
 for path,text in texts(src,wanted):
  rel=os.path.relpath(path,src).replace(os.sep,'/');base=rel.rsplit('/',1)[-1];d=os.path.dirname(rel)
  try:
   if base in READERS:READERS[base](out,rel,text)
   elif base in LOCKS:locks.setdefault(d,{}).update(_locks(rel,text,base))
   elif base.endswith('.txt') and ('requirements' in base or d.split('/')[-1]=='requirements'):_requirements(out,rel,text)
  except (ValueError,tomllib.TOMLDecodeError,AttributeError,TypeError):continue
 for k,e in out.items():
  for s in sorted(e['sources']):
   v=locks.get(os.path.dirname(s),{}).get(k)
   if v:e['installed']=v;break
 return {k:{'name':e['name'],'declared':e['declared'],'groups':sorted(e['groups']),'installed':e['installed'],'sources':sorted(e['sources'])} for k,e in out.items()}
def unlisted(found,rows):
 """[ecosystem, name, version] for every package a manifest names that the stack analyser did not list (it reads neither
 PEP 735 [dependency-groups] nor [build-system] requires, nor tools installed in workflows)."""
 have={key(e,n) for e,n,_ in rows}
 return [[k[0],e['name'],e['declared'] or e['installed'] or 'unknown'] for k,e in sorted(found.items()) if k not in have]
def attach(deps,found):
 """Give every dependency row its groups (Docker images run, Actions are CI), its manifests, and the installed version when the
 manifest gives only a range."""
 for d in deps:
  if d.get('ecosystem') in BY_ECOSYSTEM:d['groups']=[BY_ECOSYSTEM[d['ecosystem']]];continue
  e=found.get(key(d.get('ecosystem'),d.get('name','')))
  d['groups']=e['groups'] if e else []
  if not e:continue
  d['sources']=e['sources']
  if e['installed'] and not is_exact(d.get('version')) and e['installed']!=d.get('version'):d['installed']=e['installed']
