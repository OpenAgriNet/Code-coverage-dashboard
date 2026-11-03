"""What a Docker image is, read from Docker Hub so a new image needs no config: the first category its Docker Hub page is filed under
("Databases & storage", "Monitoring & observability"), as Docker Hub writes it. An image Docker Hub files under no category (or that
lives on another registry) gets no kind; nothing is guessed, renamed or defaulted."""
from common.log import warn
from common.safehttp import get as safe_get
from stackinfo.lookups import registry
CACHE={}

def hub_categories(name,get=None):
 """Names of the Docker Hub categories an image is filed under, in Docker Hub's order; [] for images on other registries."""
 host,path=registry.split(name)
 if host!='registry-1.docker.io':return []
 r=(get or safe_get)(f'https://hub.docker.com/v2/repositories/{path}/')
 return [c['name'] for c in (r.json().get('categories') or []) if isinstance(c,dict) and c.get('name')] if r.status_code==200 else []
def add_kinds(deps,hub=hub_categories,cache=CACHE,log=warn):
 """Add kind to every Docker image Docker Hub files under a category. A failed Docker Hub lookup counts as no category."""
 for d in deps:
  if d.get('ecosystem')!='docker':continue
  name=d.get('name','')
  if name not in cache:
   try:cache[name]=hub(name) if registry.NAME.fullmatch(name) else []
   except Exception as e:cache[name]=[];log(f'WARN Docker Hub categories lookup failed for {name}: {e}')
  if cache[name]:d['kind']=cache[name][0]
