"""Terraform / OpenTofu providers: the latest release from the provider registry, and the GitHub repository the provider is
built from (registries require it to be named terraform-provider-<type>), which gives its license and stars."""
import re
from common.log import warn
from common.safehttp import get as _get
from common.versions import PRERELEASE, vkey
from stackinfo.rules.reasons import short_error
NAME=re.compile(r'(?:(?P<host>[a-z0-9.-]+\.[a-z]{2,})/)?(?P<ns>[A-Za-z0-9_-]+)/(?P<type>[a-z0-9_-]+)')
CACHE={}
# Only these registries require a provider to be built from <namespace>/terraform-provider-<type>. On any other registry that name
# says nothing: registry.example.com/hashicorp/aws would borrow HashiCorp's license and stars.
TRUSTED_REGISTRIES=('registry.terraform.io','registry.opentofu.org')

def parse(name):
 """(registry host, namespace, type) of a provider address such as registry.opentofu.org/hashicorp/aws, or None."""
 m=NAME.fullmatch(name or '')
 return (m.group('host') or 'registry.opentofu.org',m.group('ns'),m.group('type')) if m else None
def latest(host,ns,typ,get=_get):
 """Newest stable version from the provider registry protocol (GET /v1/providers/<ns>/<type>/versions)."""
 r=get(f'https://{host}/v1/providers/{ns}/{typ}/versions');r.raise_for_status()
 vs=[v.get('version') for v in r.json().get('versions') or [] if v.get('version') and not PRERELEASE.search(v['version'])]
 return max(vs,key=vkey,default=None)
def annotate(deps,get=_get,cache=CACHE,log=warn):
 for d in deps:
  if d.get('ecosystem')!='terraform':continue
  p=parse(d['name'])
  if not p:log(f'WARN terraform provider not checked: {d["name"]}');continue
  if p[0] in TRUSTED_REGISTRIES:d['project']=f'github.com/{p[1]}/terraform-provider-{p[2]}'   # license and stars come from here
  if p not in cache:
   try:cache[p]={'latest':latest(*p,get=get)}
   except Exception as e:cache[p]={'errors':{'latest':f'{p[0]}: {short_error(e)}'}};log(f'WARN terraform registry {d["name"]}: {e}')
  d.update({k:(dict(v) if isinstance(v,dict) else v) for k,v in cache[p].items()})
