import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.lookups import stars as s

def test_source_repo_per_ecosystem():
    assert s.source_repo({'ecosystem': 'githubAction', 'name': 'github/codeql-action/init'}) == 'github/codeql-action'
    assert s.source_repo({'ecosystem': 'githubAction', 'name': './.github/actions/x'}) is None
    assert s.source_repo({'ecosystem': 'golang', 'name': 'github.com/jackc/pgx/v5'}) == 'jackc/pgx'
    assert s.source_repo({'ecosystem': 'golang', 'name': 'golang.org/x/tools'}) is None
    assert s.source_repo({'ecosystem': 'npm', 'name': 'react', 'project': 'github.com/facebook/react'}) == 'facebook/react'
    assert s.source_repo({'ecosystem': 'python', 'name': 'x', 'project': 'gitlab.com/a/b'}) is None
    assert s.source_repo({'ecosystem': 'npm', 'name': 'x', 'project': 'github.com/../evil'}) is None

def test_annotate_github_and_docker_hub_stars_once_each():
    calls = []
    def api(repo):
        calls.append(repo)
        return {'facebook/react': 230000, 'actions/cache': 4800}.get(repo)
    hub_calls = []
    def hub(name):
        hub_calls.append(name)
        return 15045 if name == 'postgres' else None
    deps = [{'ecosystem': 'npm', 'name': 'react', 'project': 'github.com/facebook/react'},
            {'ecosystem': 'npm', 'name': 'react-dom', 'project': 'github.com/facebook/react'},
            {'ecosystem': 'githubAction', 'name': 'actions/cache'},
            {'ecosystem': 'docker', 'name': 'postgres'}, {'ecosystem': 'docker', 'name': 'ghcr.io/o/app'},
            {'ecosystem': 'golang', 'name': 'golang.org/x/tools'}]
    s.annotate(deps, api=api, hub=hub, cache={})
    assert [d.get('stars') for d in deps] == [230000, 230000, 4800, 15045, None, None]
    assert deps[0]['stars_of'] == 'github.com/facebook/react' and deps[3]['stars_of'] == 'hub.docker.com/_/postgres'
    assert calls.count('facebook/react') == 1 and hub_calls == ['postgres']

def test_failed_lookups_leave_no_stars():
    def boom(path):
        raise RuntimeError('rate limited')
    deps = [{'ecosystem': 'githubAction', 'name': 'x/y'}]
    logs = []
    s.annotate(deps, api=boom, hub=boom, cache={}, log=logs.append)
    assert 'stars' not in deps[0] and logs

def test_hub_stars_only_for_docker_hub_images():
    got = []
    def get(url):
        got.append(url)
        class R:
            status_code = 200
            def json(self):
                return {'star_count': 7}
        return R()
    assert s.hub_stars('grafana/loki', get=get) == 7 and s.hub_stars('ghcr.io/o/app', get=get) is None
    assert s.hub_stars('postgres', get=get) == 7
    assert got == ['https://hub.docker.com/v2/repositories/grafana/loki/', 'https://hub.docker.com/v2/repositories/library/postgres/']

def test_only_whole_numbers_become_stars():
    deps = [{'ecosystem': 'githubAction', 'name': 'a/b'}, {'ecosystem': 'githubAction', 'name': 'c/d'}, {'ecosystem': 'githubAction', 'name': 'e/f'}]
    answers = {'a/b': '<img src=x onerror=alert(1)>', 'c/d': -5, 'e/f': 7}
    s.annotate(deps, api=lambda repo: answers[repo], cache={})
    assert [d.get('stars') for d in deps] == [None, None, 7]
