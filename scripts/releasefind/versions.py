"""Turn a branch, tag or release name into a comparable version (pure, no network)."""
import re
from repoconfig.config import RELEASE_DEFAULTS
NUMBER=re.compile(r'(\d+(?:\.\d+)*)(?:-(.+))?$')
PRE_ORDER=('dev','alpha','beta','pre','rc')  # unknown labels rank lowest

def parse(kind,name,rcfg):
 """{'version','identity','sort','pre'} for a ref that looks like a version, else None.
 Branches must start with branch_prefix; tags and releases are matched with tag_pattern."""
 if kind=='branch':
  if not name.startswith(rcfg['branch_prefix']):return None
  m=re.match(RELEASE_DEFAULTS['tag_pattern'],name[len(rcfg['branch_prefix']):])
 else:m=re.match(rcfg['tag_pattern'],name)
 n=NUMBER.match(m.group('version')) if m else None
 if not n:return None
 nums=tuple(int(x) for x in n.group(1).split('.'));pre=n.group(2);padded=nums+(0,)*(3-len(nums))
 label=re.match(r'[A-Za-z]*',pre or '').group(0).lower()
 rank=(PRE_ORDER.index(label) if label in PRE_ORDER else -1,tuple(int(x) for x in re.findall(r'\d+',pre or '')))
 return {'version':n.group(1)+(f'-{pre}' if pre else ''),'identity':(padded,(pre or '').lower()),'sort':(padded,0 if pre else 1,rank),'pre':pre}
