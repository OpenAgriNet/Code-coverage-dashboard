"""Stack records for the working branch and the default branch of every repo."""
import sys
import aggregate_coverage as ac
from .log import warn
from .record import stack_record

def collect(targets,policy=None,stack=None,record=stack_record,default_branch=ac.default_branch,log=warn):
 """{'repositories': working-branch records, 'main': default-branch records}.
 A repo whose working branch is its default branch is analysed once and appears in both."""
 dev,main=[],[]
 for t in targets:
  r=record(t,policy=policy,stack=stack);dev.append(r)
  try:d=default_branch(t['name'])
  except Exception as e:log(f'ERROR {t["name"]} default branch: {e}');d=None
  main.append(r if d is None or r['branch']==d else record({**t,'branch':d,'branch_source':'default'},policy=policy,stack=stack))
 return {'repositories':dev,'main':main}
