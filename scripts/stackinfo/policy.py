"""Green, yellow or red for a license, from the lists under "licenses" in config/repos.json (pure, no network).

A license is an SPDX expression: ids joined by AND / OR (AND binds tighter), parentheses, and `id WITH exception`.
A comma list ("MIT, Apache-2.0", how several licenses reported for one package are shown) means all of them apply.
Anything that does not parse is 'unclassified', never the friendlier reading."""
import re
from fnmatch import fnmatchcase
RANK={'green':0,'yellow':1,'unclassified':2,'red':3}  # for AND the worse one counts, for OR the better one
TOKEN=re.compile(r'\s*(\(|\)|[^\s()]+)')

def classify_id(lic,policy):
 """One SPDX id. Entries may be patterns (GPL-*), compared ignoring case; if lists overlap the most restrictive wins."""
 l=lic.strip().lower()
 hits=[c for c in ('green','yellow','red') if any(fnmatchcase(l,p.lower()) for p in policy.get(c,[]))]
 return max(hits,key=RANK.get) if hits else 'unclassified'
def tokens(expr):
 out=[];pos=0;expr=expr.strip()
 while pos<len(expr):
  m=TOKEN.match(expr,pos)
  if not m:raise ValueError('bad license expression')
  pos=m.end()
  out+=[x for x in re.split(r'(,)',m.group(1)) if x]  # a comma separates like AND
 return ['AND' if t==',' else t for t in out]
def parse(toks,policy):
 """Recursive descent over expr := term (OR term)*, term := factor (AND factor)*, factor := '(' expr ')' | id [WITH id]."""
 i=0
 def peek():return toks[i] if i<len(toks) else None
 def take():
  nonlocal i
  if i>=len(toks):raise ValueError('unexpected end')
  i+=1;return toks[i-1]
 def factor():
  t=take()
  if t=='(':
   c=expr()
   if take()!=')':raise ValueError('missing )')
   return c
  if t in(')','AND','OR','WITH'):raise ValueError(f'unexpected {t}')
  if peek()=='WITH':
   take();exc=take()
   full=classify_id(f'{t} WITH {exc}',policy)
   return full if full!='unclassified' else classify_id(t,policy)  # an exception can be listed on its own; otherwise the base license decides
  return classify_id(t,policy)
 def term():
  c=[factor()]
  while peek()=='AND':take();c.append(factor())
  return max(c,key=RANK.get)
 def expr():
  c=[term()]
  while peek()=='OR':take();c.append(term())
  return min(c,key=RANK.get)
 result=expr()
 if i!=len(toks):raise ValueError(f'unexpected {toks[i]}')
 return result
def classify(expr,policy):
 """None when there is no license; otherwise green, yellow, red or unclassified (also for an expression that does not parse)."""
 if not expr or not str(expr).strip():return None
 try:return parse(tokens(str(expr)),policy)
 except ValueError:return 'unclassified'
