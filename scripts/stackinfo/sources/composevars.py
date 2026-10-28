"""Image tags written as ${VAR} or ${VAR:-default}: the value the repository itself gives."""
import re
from stackinfo.sources.files import texts

def resolve_image_versions(raw,src):
 """stack-analyser keeps an image tag like ${POSTGRES_VERSION:-17} only up to the first colon. Replace such a tag with the value the
 repo itself gives: the compose default (${VAR:-17} or ${VAR-17}) on that image's line, else VAR=value from an .env example file.
 A tag no file defines is left as it is."""
 deps=raw.get('dependencies') or []
 todo=[d for d in deps if isinstance(d,list) and len(d)==3 and d[0]=='docker' and str(d[2]).startswith('${')]
 if not todo:return raw
 compose=list(texts(src,lambda n:n.endswith(('.yml','.yaml')) or n.startswith('Dockerfile')))
 env={}
 for _,t in texts(src,lambda n:n.startswith('.env') or n.endswith('.env.example')):
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
