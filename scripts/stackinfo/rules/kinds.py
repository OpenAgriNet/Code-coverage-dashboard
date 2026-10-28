"""What a Docker image is (Database, Cache, Observability, ...), so the dashboard can say that instead of naming a registry.
The first keyword of dependencies.image_kinds that the image's full name contains decides; else dependencies.default_image_kind."""
from stackinfo import settings
from stackinfo.lookups.registry import canonical

def image_kind(name):
 full=canonical(name).lower()
 return next((kind for key,kind in settings.get('image_kinds').items() if key in full),settings.get('default_image_kind'))
def add_kinds(deps):
 for d in deps:
  if d.get('ecosystem')=='docker':d['kind']=image_kind(d.get('name',''))
