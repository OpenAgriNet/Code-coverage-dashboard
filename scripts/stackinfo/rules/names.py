"""Short display names: the last path segment of a dependency name, keeping a major-version suffix with its parent.
The full name stays in `name` (links, lookups, search); the page shows `short` and puts `name` in the tooltip."""
import re
MAJOR=re.compile(r'v\d+')

def short_name(eco,name):
 """github.com/jackc/pgx/v5 -> pgx/v5, github.com/google/uuid -> uuid, @tanstack/react-query -> react-query,
 docker.langfuse.com/langfuse/langfuse:4 -> langfuse, actions/cache -> cache; local actions (./...) keep their path."""
 if eco=='githubAction' and name.startswith('./'):return name
 p=[x for x in name.split('/') if x]
 if not p:return name
 return '/'.join(p[-2:]) if len(p)>1 and MAJOR.fullmatch(p[-1]) else p[-1]
def add_short(deps):
 for d in deps:d['short']=short_name(d.get('ecosystem'),d.get('name',''))
