"""Read text files from an untrusted clone: regular files only, never symlinks, capped in size."""
import os, stat
SKIP_DIRS={'.git','node_modules','vendor','.venv'}
MAX_TEXT_BYTES=1_000_000
def texts(src,want):
 """(path, text) of the files under src whose name passes want(name). Only regular files up to MAX_TEXT_BYTES are read:
 the clone is untrusted, and a symlink such as .env -> /proc/self/environ would otherwise put the runner's secrets into
 published versions (a FIFO or a huge file would hang the run). Unreadable files are skipped."""
 for root,dirs,files in os.walk(src):
  dirs[:]=[d for d in dirs if d not in SKIP_DIRS]
  for n in files:
   if not want(n):continue
   p=os.path.join(root,n)
   try:
    st=os.lstat(p)
    if not stat.S_ISREG(st.st_mode) or st.st_size>MAX_TEXT_BYTES:continue
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,encoding='utf-8',errors='replace') as f:yield p,f.read(MAX_TEXT_BYTES)
   except OSError:continue
