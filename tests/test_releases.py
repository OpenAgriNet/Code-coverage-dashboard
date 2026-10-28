import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.lookups import releases as rl, stars
from stackinfo.rules import reasons

def test_unpinned_release_tool_is_checked_at_the_latest_release():
    api = lambda path: {'/repos/aquasecurity/trivy/releases/latest': {'tag_name': 'v0.70.0'}}.get(path)
    checked = []
    def check(deps):
        checked.extend((d['name'], d['version']) for d in deps)
        for d in deps:
            d['vulns'] = {'count': 0, 'checked_version': d['version']}
    deps = [{'ecosystem': 'githubRelease', 'name': 'aquasecurity/trivy', 'version': 'latest'}]
    rl.annotate(deps, api=api, is_go=lambda m: True, check=check, cache={})
    d = deps[0]
    assert d['latest'] == 'v0.70.0' and d['resolved'] == 'v0.70.0' and d['vulns']['count'] == 0
    assert checked == [('github.com/aquasecurity/trivy', 'v0.70.0')] and stars.source_repo(d) == 'aquasecurity/trivy'

def test_non_go_tool_is_explained_not_checked():
    api = lambda path: {'tag_name': 'v1.0.0'} if path.endswith('releases/latest') else None
    deps = [{'ecosystem': 'githubRelease', 'name': 'x/tool', 'version': 'v0.9.0'}]
    rl.annotate(deps, api=api, is_go=lambda m: False, check=lambda d: 1 / 0, cache={})
    reasons.explain(deps)
    assert deps[0]['latest'] == 'v1.0.0' and 'resolved' not in deps[0]
    assert 'not a Go module' in deps[0]['missing']['vulns']['why']

def test_when_github_refuses_the_latest_release_comes_from_deps_dev(monkeypatch):
    def forbidden(path):
        raise RuntimeError('403 Client Error: Forbidden')
    monkeypatch.setattr(rl, 'depsdev_fetch', lambda path: {'versions': [{'versionKey': {'version': 'v0.76.1'}, 'isDefault': True}]})
    checked = []
    def check(deps):
        checked.extend(d['version'] for d in deps)
        for d in deps:
            d['vulns'] = {'count': 1}
    deps = [{'ecosystem': 'githubRelease', 'name': 'aquasecurity/trivy', 'version': 'latest'}]
    rl.annotate(deps, api=forbidden, is_go=lambda m: True, check=check, cache={}, log=lambda m: None)
    assert deps[0]['latest'] == 'v0.76.1' and deps[0]['resolved'] == 'v0.76.1' and checked == ['v0.76.1'] and 'errors' not in deps[0]
    assert deps[0]['project'] == 'github.com/aquasecurity/trivy'

def test_the_repository_is_kept_even_when_every_lookup_fails():
    def boom(path):
        raise RuntimeError('403 Client Error: Forbidden')
    deps = [{'ecosystem': 'githubRelease', 'name': 'x/tool', 'version': 'latest'}]
    rl.annotate(deps, api=boom, is_go=lambda m: False, check=lambda d: None, cache={}, log=lambda m: None)
    assert deps[0]['project'] == 'github.com/x/tool' and stars.source_repo(deps[0]) == 'x/tool'
    assert '403' in deps[0]['errors']['latest']
    reasons.explain(deps)
    assert deps[0]['missing']['latest']['why'].startswith('GitHub lookup failed')
