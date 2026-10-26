import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from urllib.parse import unquote
from repoconfig import sources as s

def test_full_query_adds_org_and_forks():
    q = s.full_query({'query': 'props.project-name:"OAN DPG"'}, 'Org')
    assert q == 'org:Org props.project-name:"OAN DPG" fork:true'

def test_full_query_respects_explicit_org_fork_and_opt_out():
    assert s.full_query({'query': 'org:Other topic:x fork:only'}, 'Org') == 'org:Other topic:x fork:only'
    assert s.full_query({'query': 'topic:x', 'include_forks': False}, 'Org') == 'org:Org topic:x'

def test_query_repos_paginates_and_marks_private():
    pages = {1: {'items': [{'name': f'r{i}', 'private': False} for i in range(100)]}, 2: {'items': [{'name': 'last', 'private': True}]}}
    seen = []
    def get(path):
        seen.append(unquote(path))
        return pages[int(path.rsplit('page=', 1)[1])]
    got = s.query_repos({'query': 'topic:x'}, 'Org', get)
    assert len(got) == 101 and got[-1] == {'name': 'last', 'private': True}
    assert seen[0].startswith('/search/repositories?q=org:Org topic:x fork:true&per_page=100&page=1')

def test_query_repos_rejects_incomplete_results():
    with pytest.raises(RuntimeError, match='incomplete'):
        s.query_repos({'query': 'x'}, 'Org', lambda p: {'items': [], 'incomplete_results': True})

class Resp:
    def __init__(self, j): self.j = j
    def raise_for_status(self): pass
    def json(self): return self.j

def board(*repos, nxt=False):
    nodes = [{'content': {'repository': {'nameWithOwner': r, 'isPrivate': priv}}} for r, priv in repos]
    return Resp({'data': {'organization': {'projectV2': {'items': {'pageInfo': {'hasNextPage': nxt, 'endCursor': 'c'}, 'nodes': nodes}}}}})

def test_project_repos_keeps_same_org_only_and_flags_private():
    post = lambda *a, **k: board(('Org/a', False), ('Org/b', True), ('Other/c', False), ('Org/a', False))
    assert s.project_repos({'number': 9}, 'Org', 'tok', post) == [{'name': 'a', 'private': False}, {'name': 'b', 'private': True}]

def test_project_repos_needs_token():
    with pytest.raises(RuntimeError, match='DPG_PROJECT_TOKEN'):
        s.project_repos({'number': 9}, 'Org', None)

def test_query_repos_rejects_a_result_set_cut_off_by_the_search_limit():
    full = {'items': [{'name': 'r', 'private': False} for _ in range(100)]}
    with pytest.raises(RuntimeError, match='narrow the query'):
        s.query_repos({'query': 'topic:x'}, 'Org', lambda p: full)
