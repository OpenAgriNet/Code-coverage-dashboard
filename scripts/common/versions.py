"""Version string helpers (pure, no network)."""
import re
PRERELEASE=re.compile(r'-|(?:a|b|c|rc|dev|alpha|beta|pre)\.?\d*$',re.I)  # semver '-rc.1', PEP 440 'b1'/'rc2'/'.dev6'; '.post1' stays stable

def clean_version(v):
 """'^1.2.6' -> '1.2.6', '>=2.0,<3' -> '2.0'; None for 'latest', '*' or ${VARS}."""
 m=re.search(r'v?\d+(?:\.[0-9A-Za-z-]+)*',str(v or '').split(',')[0])
 return m.group(0) if m and '$' not in str(v) else None
def latest_stable(versions):
 """deps.dev's default version, unless it is a pre-release (PyPI often marks e.g. 1.0.0.dev6 default); then the newest stable one."""
 stable=lambda v:not PRERELEASE.search(v['versionKey']['version'])
 d=next((v for v in versions if v.get('isDefault')),None)
 if d and stable(d):return d['versionKey']['version']
 s=max((v for v in versions if stable(v)),key=lambda v:v.get('publishedAt') or '',default=None)
 return (s or d or {}).get('versionKey',{}).get('version')
PRE=re.compile(r'[-.]?(?:a|b|c|rc|dev|alpha|beta|pre)\d*',re.I)
def vkey(v):
 """Sort key: the release numbers (padded to three), then a final release above its own pre-releases (2.0.0-rc.1 < 2.0.0)."""
 m=re.match(r'v?(\d+(?:\.\d+)*)(.*)$',str(v).strip())
 if not m:return ((0,0,0),0)
 nums=tuple(int(x) for x in m.group(1).split('.'))
 return (nums+(0,)*(3-len(nums)),0 if PRE.search(m.group(2)) else 1)
def normal(name):
 return re.sub(r'[-_.]+','-',name).lower()
def is_exact(declared):
 """A pin (1.2.3, v1.2.3, ==1.2.3, =1.2.3) rather than a range (^1.2.3, >=1, 1.x)."""
 d=re.sub(r'^={1,2}','',str(declared).strip())
 return bool(re.match(r'v?\d',d)) and not any(c in d for c in '^~<>=*|, x')
