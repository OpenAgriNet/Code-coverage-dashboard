#!/usr/bin/env python3
"""Write data/stack.json: stack, dependencies and licenses for every tracked repo (see scripts/stackinfo/)."""
import json, os, sys
from datetime import datetime, timezone
import aggregate_coverage as ac
from repoconfig import resolve
from repoconfig.resolve import SourceError
from stackinfo.analyser import ANALYSER
from stackinfo.collect import collect

def main():
 try:targets=resolve(ac.CFG,ac.ORG,ac.api,ac.PROJECT_TOKEN)
 except SourceError as e:sys.exit(f'ERROR {e}')
 d=collect(targets,policy=ac.CFG['licenses'],stack=ac.CFG['stack'])
 os.makedirs('data',exist_ok=True)
 with open('data/stack.json','w',encoding='utf-8') as f:json.dump({'organization':ac.ORG,'generated_at':datetime.now(timezone.utc).isoformat(),'analyser':ANALYSER,'license_policy':ac.CFG['licenses'],**d},f,indent=2);f.write('\n')
 rows=d['repositories']
 print(f"Wrote data/stack.json for {len(rows)} repos ({sum(r['branch']!=m['branch'] for r,m in zip(rows,d['main']))} also analysed on their default branch); {sum(len(r['dependencies']) for r in rows)} dependencies.")
if __name__=='__main__':main()
