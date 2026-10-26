"""Ways to find repositories: a GitHub search query, or the issues and PRs of an org project board.
Each returns [{'name','private'}]; callers decide what to do with private ones."""
from urllib.parse import quote
import requests
PAGE=100; MAX_PAGES=10  # GitHub search stops at 1000 results
PROJECT_QUERY="""query($org:String!,$num:Int!,$after:String){organization(login:$org){projectV2(number:$num){
 items(first:100,after:$after){pageInfo{hasNextPage endCursor}
  nodes{content{... on Issue{repository{nameWithOwner isPrivate}} ... on PullRequest{repository{nameWithOwner isPrivate}}}}}}}}"""

def full_query(src,org):
 """The user's query plus `org:` and, unless include_forks is false, `fork:true` (search hides forks by default)."""
 q=src['query'].strip()
 if 'org:' not in q:q=f'org:{org} {q}'
 if src.get('include_forks',True) and 'fork:' not in q:q+=' fork:true'
 return q
def query_repos(src,org,get):
 """Repos matching a GitHub repository-search query, e.g. props.project-name:"OAN DPG". Raises if GitHub says the results are incomplete."""
 q=quote(full_query(src,org),safe='');out=[]
 for page in range(1,MAX_PAGES+1):
  d=get(f'/search/repositories?q={q}&per_page={PAGE}&page={page}') or {}
  if d.get('incomplete_results'):raise RuntimeError('GitHub search returned incomplete results')
  items=d.get('items',[]);out+=[{'name':i['name'],'private':bool(i.get('private'))} for i in items]
  if len(items)<PAGE:break
 return out
def project_repos(src,org,token,post=requests.post):
 """Repos of `org` that have an issue or PR on the project board. Needs a token that can read projects."""
 if not token:raise RuntimeError('needs the DPG_PROJECT_TOKEN secret')
 owner_org=src.get('org',org);out={};after=None
 while True:
  r=post('https://api.github.com/graphql',json={'query':PROJECT_QUERY,'variables':{'org':owner_org,'num':int(src['number']),'after':after}},headers={'Authorization':'Bearer '+token},timeout=45)
  r.raise_for_status();j=r.json()
  if j.get('errors'):raise RuntimeError(j['errors'][0].get('message'))
  items=j['data']['organization']['projectV2']['items']
  for n in items['nodes']:
   repo=((n or {}).get('content') or {}).get('repository') or {}
   owner,_,name=(repo.get('nameWithOwner') or '').partition('/')
   if name and owner.lower()==org.lower():out[name]={'name':name,'private':repo.get('isPrivate') is not False}
  if not items['pageInfo']['hasNextPage']:return sorted(out.values(),key=lambda x:x['name'])
  after=items['pageInfo']['endCursor']
