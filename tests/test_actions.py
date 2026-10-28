import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import actions as a

SHA = '55cc8345863c7cc4c66a329aec7e433d2d1c52a9'
ADVISORY = {'ghsa_id': 'GHSA-mrrh-fwg8-r2c3', 'cve_id': 'CVE-2025-30066', 'severity': 'high', 'withdrawn_at': None,
            'summary': 'tj-actions changed-files through 45.0.7 allows remote attackers to discover secrets.',
            'html_url': 'https://github.com/advisories/GHSA-mrrh-fwg8-r2c3',
            'vulnerabilities': [{'package': {'ecosystem': 'actions', 'name': 'tj-actions/changed-files'},
                                 'vulnerable_version_range': '<= 45.0.7', 'first_patched_version': '46.0.1'}]}

def fake_api(routes):
    calls = []
    def api(path):
        calls.append(path)
        return routes.get(path)
    api.calls = calls
    return api

def test_repo_of_drops_sub_path():
    assert a.repo_of('github/codeql-action/init') == 'github/codeql-action'
    assert a.repo_of('actions/cache') == 'actions/cache'

def test_floating_major_tag_resolves_to_newest_matching_tag():
    api = fake_api({'/repos/actions/cache/git/matching-refs/tags/v4.': [
        {'ref': 'refs/tags/v4.2.3'}, {'ref': 'refs/tags/v4.10.0'}, {'ref': 'refs/tags/v4.3.0'}, {'ref': 'refs/tags/v4.3.0-beta'}]})
    assert a.resolve('actions/cache', 'v4', api) == 'v4.10.0'

def test_major_tag_does_not_match_a_longer_major():
    api = fake_api({'/repos/x/y/git/matching-refs/tags/v4.': []})
    assert a.resolve('x/y', 'v4', api) == 'v4'   # the tag itself is the best we know; v40.1.0 is never asked for

def test_full_tag_is_used_as_is():
    api = fake_api({})
    assert a.resolve('x/y', 'v4.2.1', api) == 'v4.2.1' and api.calls == []

def test_commit_pin_maps_to_its_tag_or_none():
    api = fake_api({'/repos/actions/cache/tags?per_page=100': [{'name': 'v6.1.0', 'commit': {'sha': SHA}}]})
    assert a.resolve('actions/cache', SHA, api) == 'v6.1.0'
    assert a.resolve('actions/cache', 'f' * 40, api) is None

def test_branch_ref_is_not_a_version():
    assert a.resolve('x/y', 'main', fake_api({})) is None

def test_latest_prefers_latest_release_then_highest_tag():
    assert a.latest('actions/cache', fake_api({'/repos/actions/cache/releases/latest': {'tag_name': 'v6.1.0'}})) == 'v6.1.0'
    api = fake_api({'/repos/x/y/tags?per_page=100': [{'name': 'v1.2.0'}, {'name': 'v1.10.0'}, {'name': 'nightly'}]})
    assert a.latest('x/y', api) == 'v1.10.0'

def test_advisories_become_vulnerability_items():
    api = fake_api({'/advisories?ecosystem=actions&affects=tj-actions/changed-files@45.0.7&per_page=100': [ADVISORY]})
    items = a.advisories('tj-actions/changed-files', 'v45.0.7', api)
    assert items == [{'id': 'GHSA-mrrh-fwg8-r2c3', 'cve': 'CVE-2025-30066', 'severity': 'HIGH', 'fixed': '46.0.1',
                      'summary': ADVISORY['summary'], 'url': ADVISORY['html_url']}]

def test_withdrawn_advisories_are_dropped_and_medium_reads_moderate():
    medium = {**ADVISORY, 'ghsa_id': 'GHSA-b', 'severity': 'medium', 'vulnerabilities': [{**ADVISORY['vulnerabilities'][0], 'first_patched_version': {'identifier': '47'}}]}
    api = fake_api({'/advisories?ecosystem=actions&affects=tj-actions/changed-files@45.0.7&per_page=100': [{**ADVISORY, 'withdrawn_at': '2025-01-01'}, medium]})
    items = a.advisories('tj-actions/changed-files', '45.0.7', api)
    assert [(i['id'], i['severity'], i['fixed']) for i in items] == [('GHSA-b', 'MODERATE', '47')]

def test_annotate_fills_action_rows_and_leaves_others():
    api = fake_api({
        '/repos/tj-actions/changed-files/git/matching-refs/tags/v45.': [{'ref': 'refs/tags/v45.0.7'}],
        '/repos/tj-actions/changed-files/releases/latest': {'tag_name': 'v47.0.0'},
        '/repos/tj-actions/changed-files/license': {'license': {'spdx_id': 'MIT'}},
        '/advisories?ecosystem=actions&affects=tj-actions/changed-files@45.0.7&per_page=100': [ADVISORY]})
    act = {'ecosystem': 'githubAction', 'name': 'tj-actions/changed-files', 'version': 'v45', 'latest': None, 'license': None, 'license_of': None, 'vulns': None}
    local = {'ecosystem': 'githubAction', 'name': './.github/actions/x', 'version': 'latest', 'vulns': None}
    npm = {'ecosystem': 'npm', 'name': 'left', 'version': '1.0.0', 'vulns': {'count': 0}}
    a.annotate([act, local, npm], api=api, cache={})
    assert act['resolved'] == 'v45.0.7' and act['latest'] == 'v47.0.0' and act['license'] == 'MIT' and act['license_of'] == 'repo'
    assert act['vulns']['count'] == 1 and act['vulns']['fixed_in'] == '46.0.1' and act['vulns']['checked_version'] == 'v45.0.7' and act['vulns']['exact']
    assert local == {'ecosystem': 'githubAction', 'name': './.github/actions/x', 'version': 'latest', 'vulns': None}
    assert npm['vulns'] == {'count': 0}

def test_annotate_unmatched_commit_pin_is_not_checked():
    api = fake_api({'/repos/x/y/tags?per_page=100': [], '/repos/x/y/releases/latest': {'tag_name': 'v2.0.0'}})
    d = {'ecosystem': 'githubAction', 'name': 'x/y', 'version': 'f' * 40, 'vulns': None}
    a.annotate([d], api=api, cache={})
    assert d['vulns'] is None and d['latest'] == 'v2.0.0' and not any(p.startswith('/advisories') for p in api.calls)

def test_annotate_caches_per_action_and_survives_api_errors():
    def boom(path):
        raise RuntimeError('rate limited')
    d1 = {'ecosystem': 'githubAction', 'name': 'x/y', 'version': 'v1', 'vulns': None}
    logs = []
    a.annotate([d1], api=boom, cache={}, log=logs.append)
    assert d1['vulns'] is None and d1['license_of'] == 'error' and logs
    api = fake_api({'/repos/x/y/git/matching-refs/tags/v1.': [{'ref': 'refs/tags/v1.0.0'}]})
    cache = {}
    rows = [{'ecosystem': 'githubAction', 'name': 'x/y', 'version': 'v1', 'vulns': None} for _ in range(2)]
    a.annotate(rows, api=api, cache=cache)
    assert sum(p.startswith('/repos/x/y/git') for p in api.calls) == 1 and rows[0]['resolved'] == rows[1]['resolved'] == 'v1.0.0'

def test_malformed_names_and_refs_never_reach_the_api():
    api = fake_api({})
    rows = [{'ecosystem': 'githubAction', 'name': n, 'version': v, 'vulns': None}
            for n, v in [('../../orgs', 'v1'), ('a/..', 'v1'), ('x/y', 'v1&per_page=1'), ('x/y', '../v1'), ('.x/y', 'v1')]]
    a.annotate(rows, api=api, cache={}, log=lambda m: None)
    assert api.calls == [] and all(r['vulns'] is None and 'latest' not in r for r in rows)
