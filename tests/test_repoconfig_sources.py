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


PQ = {'query': 'props.project-name:"OAN DPG"'}

def counting(total_for_control, items=()):
    """A fake search that answers the control query (a value no repo has) with `total_for_control`."""
    seen = []
    def get(path):
        seen.append(unquote(path))
        if '__no_such_value__' in path:
            return {'total_count': total_for_control, 'items': []}
        return {'total_count': len(items), 'items': [{'name': n, 'private': False} for n in items]}
    get.seen = seen
    return get

def test_a_props_filter_that_works_is_checked_once_and_results_are_used():
    get = counting(0, ['a', 'b'])
    assert [r['name'] for r in s.query_repos(PQ, 'Org', get)] == ['a', 'b']
    assert get.seen[0] == 'org:Org props.project-name:"__no_such_value__" fork:true'.join(['/search/repositories?q=', '&per_page=1'])
    assert len(get.seen) == 2

def test_a_props_filter_that_is_silently_ignored_stops_the_run():
    get = counting(48, ['everything'])
    with pytest.raises(RuntimeError, match='ignored the props. filter.*48 repositories.*DPG_QUERY_TOKEN'):
        s.query_repos(PQ, 'Org', get)
    assert len(get.seen) == 1   # the real query is never trusted

def test_every_props_filter_in_a_query_gets_a_made_up_value():
    q = s.PROPS.sub(r'\1"__no_such_value__"', 'org:o props.a:"x y" props.b-c:z topic:t')
    assert q == 'org:o props.a:"__no_such_value__" props.b-c:"__no_such_value__" topic:t'

def test_a_query_without_props_needs_no_check():
    get = counting(99, ['a'])
    assert [r['name'] for r in s.query_repos({'query': 'topic:dpg'}, 'Org', get)] == ['a'] and len(get.seen) == 1
