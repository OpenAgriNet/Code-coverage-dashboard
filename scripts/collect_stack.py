#!/usr/bin/env python3
"""Write data/stack.json: stack, dependencies and licenses for every tracked repo (see scripts/stackinfo/)."""
import json, os
from datetime import datetime, timezone
import aggregate_coverage as ac
from stackinfo.analyser import ANALYSER
from stackinfo.record import stack_record

def main():
 dpg=ac.dpg_project_repos()
 if dpg is None:dpg=ac.CFG.get('dpg_repositories',[])
 ac.CFG['dpg_repositories']=dpg
 rows=[stack_record(t) for t in ac.repo_targets(ac.CFG,dpg)]
 os.makedirs('data',exist_ok=True)
 with open('data/stack.json','w',encoding='utf-8') as f:json.dump({'organization':ac.ORG,'generated_at':datetime.now(timezone.utc).isoformat(),'analyser':ANALYSER,'repositories':rows},f,indent=2);f.write('\n')
 print(f"Wrote data/stack.json for {len(rows)} repos; {sum(len(r['dependencies']) for r in rows)} dependencies.")
if __name__=='__main__':main()
