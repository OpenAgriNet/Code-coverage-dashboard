#!/usr/bin/env python3
"""Write data/stack.json: stack, dependencies and licenses for every tracked repo (see scripts/stackinfo/)."""
import json, os, sys
from datetime import datetime, timezone
from common import github
from repoconfig import load as load_config, resolve
from repoconfig.resolve import SourceError
from stackinfo.sources.analyser import ANALYSER
from stackinfo import settings
from stackinfo.lookups import licensetext
from stackinfo.pipeline import collect

def main():
 cfg=load_config('config/repos.json');settings.configure(cfg['dependencies']);licensetext.use(cfg['licenses'])
 try:targets=resolve(cfg,github.ORG,github.api,github.PROJECT_TOKEN,search_get=github.SEARCH)
 except SourceError as e:sys.exit(f'ERROR {e}')
 d=collect(targets,policy=cfg['licenses'],stack=cfg['stack'])
 os.makedirs('data',exist_ok=True)
 with open('data/stack.json','w',encoding='utf-8') as f:json.dump({'organization':github.ORG,'generated_at':datetime.now(timezone.utc).isoformat(),'analyser':ANALYSER,'license_policy':cfg['licenses'],'display':{'ecosystems':cfg['dependencies']['ecosystem_names']},**d},f,indent=2);f.write('\n')
 rows=d['repositories']
 print(f"Wrote data/stack.json for {len(rows)} repos ({sum(r['branch']!=m['branch'] for r,m in zip(rows,d['main']))} also analysed on their default branch); {sum(len(r['dependencies']) for r in rows)} dependencies.")
if __name__=='__main__':main()
