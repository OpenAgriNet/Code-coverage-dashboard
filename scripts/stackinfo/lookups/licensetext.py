"""Name a license from its text when no service can: GitHub says NOASSERTION and deps.dev 'non-standard' for the PostgreSQL License
(postgres, pgvector), though the text is the standard one, and for a file holding several licenses (Redis 7.4 and later: RSALv2 or
SSPL). The text is compared with SPDX reference texts by the words they share once copyright lines are dropped; the best one is taken
only when it is clearly alike (MATCH) and clearly ahead of the next (MARGIN). The candidates are the licenses the policy in
config/repos.json names exactly and the SPDX licenses the text itself names (by id, or by name without its version). A file whose
sections are headed and underlined (=====) and that matches no single license is read section by section. No license is named by hand."""
import re
from common.safehttp import get as safe_get
SPDX='https://raw.githubusercontent.com/spdx/license-list-data/main/text/{}.txt'
INDEX='https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json'
SPDX_ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9.+-]*')
MATCH=0.8
MARGIN=0.1
MIN_SECTION=150   # words; a shorter section is a preamble, not a license
MAX_NAMED=12      # candidates taken from the names a text mentions
POLICY={}
TEXTS={}
NAMES=[]          # (spdx id, lower-case id, name without its version) from the SPDX index, read once per run
COPYRIGHT=re.compile(r'(?im)^.*(?:copyright|\(c\)|portions).*$')
HEADING=re.compile(r'(?m)^[ \t]*(\S[^\n]*)\n[ \t]*={4,}[ \t]*$')
# a file that offers its licenses as alternatives says so
CHOICE=re.compile(r"(?i)\b(?:choice|at your option|dual[- ]licen[sc]|tri[- ]licen[sc]|either of)")
VERSIONED=re.compile(r'(?i)[\s,]*(?:v(?:ersion)?\s*)?\d[\d.]*(?:\s+(?:only|or later))?$|\s+(?:only|or later)$')

def use(policy):
 """The license policy whose ids are candidates (config/repos.json licenses)."""
 POLICY.clear();POLICY.update(policy or {})
def words(text):
 return set(re.findall(r'[a-z0-9]+',COPYRIGHT.sub('',text).lower()))
def spdx_names(get=None):
 if not NAMES:
  r=(get or safe_get)(INDEX)
  for l in (r.json().get('licenses') or []) if r.status_code==200 else []:
   i,n=l.get('licenseId'),(l.get('name') or '').lower()
   if i and not l.get('isDeprecatedLicenseId'):NAMES.append((i,i.lower(),VERSIONED.sub('',n).strip()))
 return NAMES
def candidates(text='',get=None):
 """Exact SPDX ids the policy lists (patterns like GPL-* name no single text), and those the text names."""
 ids={p for c in ('green','yellow','red') for p in POLICY.get(c,[])}
 low=' '.join(re.findall(r'[a-z0-9.+-]+',text.lower()))
 if low:
  named=[i for i,li,base in spdx_names(get) if re.search(r'(?<![\w.+-])'+re.escape(li)+r'(?![\w+-])',low) or (len(base)>12 and base in low)]
  ids|=set(named[:MAX_NAMED])
 return sorted(p for p in ids if SPDX_ID.fullmatch(p) and not p.startswith('LicenseRef-'))
def reference(spdx_id,get=None):
 """Words of the SPDX reference text of spdx_id, or None when SPDX has none. Cached per run."""
 if spdx_id not in TEXTS:
  r=(get or safe_get)(SPDX.format(spdx_id))
  TEXTS[spdx_id]=words(r.text) if r.status_code==200 else None
 return TEXTS[spdx_id]
def best(text,get=None,named=None):
 """The one SPDX id whose reference text this text is, or None. named: the candidates, when a heading names them."""
 w=words(text or '')
 if not w:return None
 score=[]
 for i in named or candidates(text,get):
  ref=reference(i,get)
  if ref:score.append((2*len(w&ref)/(len(w)+len(ref)),i))
 score.sort(key=lambda x:(-x[0],not x[1].endswith('-only'),x[1]))   # the same text as -only and -or-later: the file states no 'or later'
 # the -only and -or-later texts of a license are the same text: a tie between them is not a doubt
 base=lambda i:re.sub(r'-(?:only|or-later)$','',i)
 rival=next((s for s,i in score[1:] if base(i)!=base(score[0][1])),0) if score else 0
 if not score or score[0][0]<MATCH or score[0][0]-rival<MARGIN:return None
 return score[0][1]
def sections(text):
 """(heading, body) of each headed section."""
 hs=list(HEADING.finditer(text))
 return [(h.group(1).strip(),text[h.end():hs[k+1].start() if k+1<len(hs) else len(text)]) for k,h in enumerate(hs)]
def unnamed(heading):
 """A LicenseRef for a section no SPDX text matches, from the short name its heading gives in brackets: RSALv2."""
 m=re.search(r'\(([A-Za-z][A-Za-z0-9.+-]{1,20})\)',heading)
 return f'LicenseRef-{m.group(1)}' if m else 'LicenseRef-Other'
def identify(text,get=None):
 """The SPDX expression this license text is, or None: one id, or for a file of several licenses each one, joined by OR when the
 file offers a choice, else AND. A section is compared with the licenses its heading names (GNU AFFERO ... Version 3: the AGPL
 texts, not GPL-3.0, which is nearly the same text), else with those its body names."""
 parts=[(h,b) for h,b in sections(text or '') if len(words(b))>=MIN_SECTION]
 if len(parts)<2:return best(text,get)
 ids=list(dict.fromkeys(best(b,get,[i for i in candidates(h,get) if i not in candidates('',get)]) or unnamed(h) for h,b in parts))
 if all(i.startswith('LicenseRef-') for i in ids):return None
 return (' OR ' if CHOICE.search(text) else ' AND ').join(ids)
