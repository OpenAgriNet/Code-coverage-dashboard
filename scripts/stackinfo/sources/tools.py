"""Tools a repository's GitHub workflows install in their run steps: a release installed with curl ... install.sh | sh
(Trivy), pip / pipx / uv tool installs, npm -g and npx, and go install. Each is grouped by what its workflow is for."""
import os, re
from stackinfo import settings
from stackinfo.sources.manifests import add_entry, pep508_name, pep508_version

# Every quantifier is bounded: workflow files come from the tracked repos, and unbounded lazy matches here took quadratic time
# (112 KB of 'install' repeated cost 8 s, 1 MB about ten minutes), enough to stall the nightly run.
CURL=re.compile(r'raw\.githubusercontent\.com/([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100})/\S{0,300}?install\S{0,100}?\.sh\S{0,100}\s{0,4}\|\s{0,4}(?:ba)?sh\b([^\n]{0,200})')
PIP=re.compile(r'(?:\bpip3?|python3? -m pip|\buv pip|\bpipx|\buv tool)\s+install\s+([^\n&|;#]+)')
NPM=re.compile(r'\bnpm\s+(?:install|i|add)\s+(?:-g|--global)\s+([^\n&|;#]+)|\bnpx\s+(?:(?:--yes|-y)\s+)?([^\s&|;#]+)')
GO=re.compile(r'\bgo\s+install\s+([A-Za-z0-9_./-]+)@(\S+)')
VERSION=re.compile(r'v?\d+\.\d+(?:\.\d+)?')
TAKES_VALUE={'-r','-c','-e','--requirement','--constraint','--editable','-i','--index-url','--extra-index-url','-f','--find-links','--python','--target','-t'}

def purpose(filename):
 """Group of a tool by the workflow that installs it: the first key of dependencies.groups.workflow_purposes the file name
 contains (security.yml -> security, run-tests.yml -> test), otherwise dependencies.groups.default_workflow_group (ci)."""
 n=filename.lower()
 g=settings.get('groups')
 return next((grp for k,grp in g['workflow_purposes'].items() if k in n),g['default_workflow_group'])
def _words(text):
 return [w.strip('\'"') for w in text.split()]
def _pip(out,args,group,rel):
 skip=False
 for w in _words(args):
  if skip:skip=False;continue
  if w in TAKES_VALUE:skip=True;continue
  if w.startswith('-') or w in ('.','..') or '/' in w or w.startswith('$'):continue
  n=pep508_name(w)
  if n:add_entry(out,'python',n,group,rel,pep508_version(w))
def _npm(out,arg,group,rel,first_only):
 for w in _words(arg)[:1] if first_only else _words(arg):
  if w.startswith('-') or w.startswith('$'):continue
  name,_,ver=w.rpartition('@') if w.rfind('@')>0 else (w,'','')
  if re.fullmatch(r'(@[a-z0-9._-]+/)?[a-z0-9._-]+',name):add_entry(out,'npm',name,group,rel,ver or None)
def read(src,texts=None):
 """Found entries ({(ecosystem, key): {...}}, as manifests.read gives) for tools installed in .github/workflows/*.yml."""
 if texts is None:
  from stackinfo.sources.files import texts as read_texts
  texts=read_texts
 out={}
 for path,text in texts(src,lambda n:n.endswith(('.yml','.yaml'))):
  rel=os.path.relpath(path,src).replace(os.sep,'/')
  if not rel.startswith('.github/workflows/'):continue
  g=purpose(rel.rsplit('/',1)[-1])
  for m in CURL.finditer(text):
   v=next((w for w in _words(m.group(3)) if VERSION.fullmatch(w)),None)
   add_entry(out,'githubRelease',f'{m.group(1)}/{m.group(2)}',g,rel,v or 'latest')
  for m in PIP.finditer(text):_pip(out,m.group(1),g,rel)
  for m in NPM.finditer(text):_npm(out,m.group(1) or m.group(2),g,rel,first_only=bool(m.group(2)))
  for m in GO.finditer(text):add_entry(out,'golang',m.group(1),g,rel,m.group(2))
 return {k:{'name':e['name'],'declared':e['declared'],'groups':sorted(e['groups']),'installed':None,'sources':sorted(e['sources'])} for k,e in out.items()}
def merge(found,tools):
 """Add workflow tools to the manifests' entries; a package both declares and installs in CI keeps both groups."""
 for k,e in tools.items():
  if k in found:
   f=found[k];f['groups']=sorted(set(f['groups'])|set(e['groups']));f['sources']=sorted(set(f['sources'])|set(e['sources']))
  else:found[k]=e
 return found
