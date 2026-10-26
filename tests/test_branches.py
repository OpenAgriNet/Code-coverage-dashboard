import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from repoconfig.branches import branch_names, find_development
from repoconfig.config import DEV_BRANCH_DEFAULT as P

def pages(names, size=100):
    def get(path):
        n = int(path.rsplit('page=', 1)[1]) - 1
        return [{'name': b} for b in names[n * size:(n + 1) * size]]
    return get

def test_branch_names_follow_pagination():
    names = [f'b{i}' for i in range(230)]
    assert branch_names('o', 'r', pages(names)) == names

def test_finds_the_usual_development_names():
    for n in ('dev', 'develop', 'development'):
        assert find_development('o', 'r', P, pages(['main', n])) == n

def test_ignores_lookalikes_and_returns_none_when_nothing_matches():
    assert find_development('o', 'r', P, pages(['main', 'devops', 'feature/dev', 'development-2', 'release-1.0.0'])) is None

def test_no_branches_at_all():
    assert find_development('o', 'r', P, pages([])) is None

def test_finds_a_branch_on_a_later_page():
    names = [f'b{i}' for i in range(150)] + ['development']
    assert find_development('o', 'r', P, pages(names)) == 'development'

def test_failure_is_logged_and_means_no_match():
    logs = []
    def boom(path):
        raise RuntimeError('502')
    assert find_development('o', 'r', P, boom, logs.append) is None and 'could not list branches' in logs[0]
