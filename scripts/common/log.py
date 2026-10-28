"""Log lines for the Actions run. Names, tags and error text come from tracked repos and remote servers, and a line that starts
with :: is an Actions workflow command (::add-mask::, ::stop-commands::), so control characters never reach the log."""
import re, sys
CONTROL=re.compile(r'[\x00-\x1f\x7f  ]')

def clean(text,limit=400):
 return CONTROL.sub('?',str(text))[:limit]
def warn(msg):
 print(clean(msg),file=sys.stderr)
