"""Name a license from its text when no service can: GitHub says NOASSERTION and deps.dev 'non-standard' for the PostgreSQL License
(postgres, pgvector), though the text is the standard one. The text is compared with the SPDX reference text of every license the
policy in config/repos.json names exactly, by the words they share once copyright lines are dropped; the best one is taken only
when it is clearly alike (MATCH) and clearly ahead of the next (MARGIN). No license is named by hand."""
import re
from common.safehttp import get as safe_get
SPDX='https://raw.githubusercontent.com/spdx/license-list-data/main/text/{}.txt'
SPDX_ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9.+-]*')
MATCH=0.8
MARGIN=0.1
POLICY={}
TEXTS={}
COPYRIGHT=re.compile(r'(?im)^.*(?:copyright|\(c\)|portions).*$')

def use(policy):
 """The license policy whose ids are the candidates (config/repos.json licenses)."""
 POLICY.clear();POLICY.update(policy or {})
def words(text):
 return set(re.findall(r'[a-z0-9]+',COPYRIGHT.sub('',text).lower()))
def candidates():
 """Exact SPDX ids the policy lists (patterns like GPL-* name no single text)."""
 return sorted({p for c in ('green','yellow','red') for p in POLICY.get(c,[]) if SPDX_ID.fullmatch(p) and not p.startswith('LicenseRef-')})
def reference(spdx_id,get=None):
 """Words of the SPDX reference text of spdx_id, or None when SPDX has none. Cached per run."""
 if spdx_id not in TEXTS:
  r=(get or safe_get)(SPDX.format(spdx_id))
  TEXTS[spdx_id]=words(r.text) if r.status_code==200 else None
 return TEXTS[spdx_id]
def identify(text,get=None):
 """The SPDX id whose reference text this license text is, or None."""
 w=words(text or '')
 if not w:return None
 score=[]
 for i in candidates():
  ref=reference(i,get)
  if ref:score.append((2*len(w&ref)/(len(w)+len(ref)),i))
 score.sort(reverse=True)
 if not score or score[0][0]<MATCH or (len(score)>1 and score[0][0]-score[1][0]<MARGIN):return None
 return score[0][1]
