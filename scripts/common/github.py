"""GitHub REST access shared by the coverage and stack collectors. The token comes from the environment; no config is read here."""
import os
import requests
API='https://api.github.com'; ORG=os.getenv('GITHUB_ORG','OpenAgriNet'); TOKEN=os.getenv('GH_TOKEN'); PROJECT_TOKEN=os.getenv('DPG_PROJECT_TOKEN'); QUERY_TOKEN=os.getenv('DPG_QUERY_TOKEN')
S=requests.Session(); S.headers.update({'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
if TOKEN: S.headers['Authorization']='Bearer '+TOKEN

def search_api(path):
 """GET for the repository search with its own token: filtering by a custom property needs one that can read the organization's custom properties."""
 r=requests.get(API+path,headers={**dict(S.headers),'Authorization':'Bearer '+QUERY_TOKEN},timeout=45)
 r.raise_for_status();return r.json()
SEARCH=search_api if QUERY_TOKEN else None
def api(path):
 r=S.get(API+path,timeout=45)
 if r.status_code in (404,409):return None  # 409: GitHub's answer for refs and commits of an empty repository
 r.raise_for_status();return r.json()
def default_branch(repo):
 return (api(f'/repos/{ORG}/{repo}') or {}).get('default_branch') or 'main'
