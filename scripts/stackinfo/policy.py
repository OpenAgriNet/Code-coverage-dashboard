"""Green, yellow or red for a license, from the lists under "licenses" in config/repos.json (pure, no network)."""
import re
from fnmatch import fnmatchcase
RANK={'green':0,'yellow':1,'unclassified':2,'red':3}  # for AND the worse one counts, for OR the better one

def classify_id(lic,policy):
 """One SPDX id. Entries may be patterns (GPL-*), compared ignoring case; if lists overlap the most restrictive wins."""
 l=lic.strip().lower()
 hits=[c for c in ('green','yellow','red') if any(fnmatchcase(l,p.lower()) for p in policy.get(c,[]))]
 return max(hits,key=RANK.get) if hits else 'unclassified'
def classify(expr,policy):
 """None when there is no license. 'A OR B' takes the better class (the user may choose), 'A AND B' the worse."""
 if not expr:return None
 ors=[max((classify_id(x.strip(' ()'),policy) for x in re.split(r'\s+AND\s+',part)),key=RANK.get) for part in re.split(r'\s+OR\s+',expr.strip())]
 return min(ors,key=RANK.get)
