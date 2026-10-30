"""What a Docker image is, shown as its ecosystem, read from the image's own homes so a new image needs no config: the first category
its Docker Hub page is filed under ("Databases & storage", "Monitoring & observability"), else the first GitHub topic of its source
repository, else dependencies.default_image_kind. The words are shown as Docker Hub or GitHub give them; nothing is renamed."""
from common.log import warn
from common.safehttp import get as safe_get
from stackinfo import settings
from stackinfo.lookups import registry
from stackinfo.lookups.repostate import topics as repo_topics
from stackinfo.lookups.stars import source_repo
CACHE={}

def hub_categories(name,get=None):
 """Names of the Docker Hub categories an image is filed under, in Docker Hub's order; [] for images on other registries."""
 host,path=registry.split(name)
 if host!='registry-1.docker.io':return []
 r=(get or safe_get)(f'https://hub.docker.com/v2/repositories/{path}/')
 return [c['name'] for c in (r.json().get('categories') or []) if isinstance(c,dict) and c.get('name')] if r.status_code==200 else []
def image_kind(categories,topics):
 """(kind, kind_of): the first Docker Hub category, else the first GitHub topic, else the default with kind_of None."""
 if categories:return categories[0],'docker hub'
 if topics:return topics[0],'github topic'
 return settings.get('default_image_kind'),None
def add_kinds(deps,hub=hub_categories,topics=repo_topics,cache=CACHE,log=warn):
 """Add kind to every Docker image, and kind_of when Docker Hub or GitHub stated it. Run after the source repositories are known
 (images, stars) and their topics read (repostate). A failed Docker Hub lookup counts as no category."""
 for d in deps:
  if d.get('ecosystem')!='docker':continue
  name=d.get('name','')
  if name not in cache:
   try:cache[name]=hub(name) if registry.NAME.fullmatch(name) else []
   except Exception as e:cache[name]=[];log(f'WARN Docker Hub categories lookup failed for {name}: {e}')
  d['kind'],of=image_kind(cache[name],topics(source_repo(d)))
  if of:d['kind_of']=of
