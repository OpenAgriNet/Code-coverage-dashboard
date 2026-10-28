"""An image's ecosystem: its vendor, read from the image's own name, so nothing has to be listed for a new image. An official
Docker Hub image is its own vendor (library/redis -> redis); any other is its namespace (grafana/loki -> grafana,
docker.langfuse.com/langfuse/langfuse -> langfuse, cgr.dev/chainguard/minio -> chainguard, ghcr.io/openagrinet/x -> openagrinet).
dependencies.image_vendor_aliases renames the few that read badly (prom -> prometheus)."""
from stackinfo import settings
from stackinfo.lookups.registry import split

def image_vendor(name):
 host,path=split(name);p=[x for x in path.split('/') if x]
 if not p:return name
 v=p[1] if host=='registry-1.docker.io' and p[0]=='library' and len(p)>1 else p[0]
 v=v.lower()
 return settings.get('image_vendor_aliases').get(v,v)
def add_vendors(deps):
 for d in deps:
  if d.get('ecosystem')=='docker':d['vendor']=image_vendor(d.get('name',''))
