"""Finding a repository's development branch."""
import re
PAGE=100; MAX_PAGES=5

def branch_names(org,repo,get):
 out=[]
 for page in range(1,MAX_PAGES+1):
  items=get(f'/repos/{org}/{repo}/branches?per_page={PAGE}&page={page}') or []
  out+=[b['name'] for b in items]
  if len(items)<PAGE:break
 return out
def find_development(org,repo,pattern,get,log=lambda m:None):
 """The first branch (alphabetically) matching `pattern`, or None. A lookup failure is logged and counts as no match."""
 try:names=branch_names(org,repo,get)
 except Exception as e:log(f'WARN {repo}: could not list branches: {e}');return None
 hits=sorted(n for n in names if re.search(pattern,n))
 if len(hits)>1:log(f'{repo}: several branches match the development pattern ({", ".join(hits)}); using {hits[0]}')
 return hits[0] if hits else None
