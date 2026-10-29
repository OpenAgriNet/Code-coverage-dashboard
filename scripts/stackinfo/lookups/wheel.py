"""License of a Python package installed from a wheel URL (en-core-web-sm from a GitHub release), which no registry knows: the
License-Expression or License field of the wheel's own METADATA. Only the zip directory and that one file are fetched, with
HTTP range requests, never the whole wheel (12 MB for a spaCy model)."""
import email.parser, io, zipfile
from common.safehttp import get as safe_get
from stackinfo import settings
MAX_READS=12   # a wheel's METADATA is found in about 4

class Remote(io.RawIOBase):
 """A read-only, seekable file over HTTP range requests."""
 def __init__(self,url,get):
  self.url,self.get,self.pos,self.reads=url,get,0,0
  self.size=int(self._range(0,0).headers['Content-Range'].rsplit('/',1)[1])
 def _range(self,a,b):
  self.reads+=1
  if self.reads>MAX_READS:raise RuntimeError(f'more than {MAX_READS} range reads')
  r=self.get(self.url,plain={'Range':f'bytes={a}-{b}','Accept-Encoding':'identity'})
  if r.status_code!=206:raise RuntimeError(f'range request answered {r.status_code}')
  return r
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,off,whence=0):
  self.pos=(off,self.pos+off,self.size+off)[whence];return self.pos
 def readinto(self,b):
  if self.pos>=self.size or not len(b):return 0
  data=self._range(self.pos,min(self.pos+len(b),self.size)-1).content[:len(b)]
  b[:len(data)]=data;self.pos+=len(data)
  return len(data)

def wheel_license(url,get=None):
 """SPDX license a wheel's METADATA states, or None. A License text is kept only when config/dependencies.json license_aliases
 names it, or when it is a single word (MIT); prose stays unnamed."""
 if not url.startswith('https://') or not url.split('?',1)[0].endswith('.whl'):return None
 with zipfile.ZipFile(io.BufferedReader(Remote(url,get or safe_get),65536)) as z:
  meta=next((n for n in z.namelist() if n.count('/')==1 and n.endswith('.dist-info/METADATA')),None)
  if not meta or z.getinfo(meta).file_size>1_000_000:return None
  m=email.parser.HeaderParser().parsestr(z.read(meta).decode('utf-8','replace'))
 if m.get('License-Expression'):return m['License-Expression'].strip()
 text=(m.get('License') or '').strip()
 alias=settings.get('license_aliases').get(text.lower())
 return alias or (text if text and ' ' not in text and text.upper() not in ('UNKNOWN','NONE') else None)
