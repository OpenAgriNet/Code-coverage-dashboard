import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from repoconfig.config import RELEASE_DEFAULTS as R
from releasefind import find_versions

def fake(branches=(), tags=(), releases=()):
    def get(path):
        if '/git/matching-refs/heads/' in path:
            return [{'ref': 'refs/heads/' + n, 'object': {'sha': s}} for n, s in branches]
        if '/tags?' in path:
            return [{'name': n, 'commit': {'sha': s}} for n, s in tags]
        if '/releases?' in path:
            return [{'tag_name': n, 'prerelease': pre, 'draft': d, 'published_at': '2026-09-18'} for n, pre, d in releases]
        raise AssertionError(path)
    return get

def find(get, **kw):
    logs = []
    return find_versions('o', 'r', {**R, **kw}, get, log=logs.append), logs

def test_merges_sources_newest_first_and_branch_wins_by_default():
    got, _ = find(fake(branches=[('release-0.2.0', 'b2')], tags=[('v0.1.0', 't1'), ('0.2.0', 't2'), ('fork-point', 'x')], releases=[('v0.1.0', False, False)]))
    assert [v['version'] for v in got['versions']] == ['0.2.0', '0.1.0']
    v2, v1 = got['versions']
    assert (v2['ref'], v2['ref_kind'], v2['sha'], v2['kinds']) == ('release-0.2.0', 'branch', 'b2', ['branch', 'tag'])
    assert (v1['ref'], v1['ref_kind'], v1['sha'], v1['kinds'], v1['published_at']) == ('v0.1.0', 'tag', 't1', ['tag', 'release'], '2026-09-18')

def test_source_order_decides_which_ref_is_measured():
    got, _ = find(fake(branches=[('release-0.2.0', 'b2')], tags=[('v0.2.0', 't2')]), sources=['tag', 'branch'])
    assert got['versions'][0]['ref'] == 'v0.2.0' and got['versions'][0]['sha'] == 't2' and got['versions'][0]['kinds'] == ['tag', 'branch']

def test_only_enabled_sources_are_used():
    got, _ = find(fake(branches=[('release-0.2.0', 'b2')], tags=[('v0.1.0', 't1')]), sources=['branch'])
    assert [v['version'] for v in got['versions']] == ['0.2.0']

def test_release_only_resolves_its_sha_from_the_tag_list():
    got, _ = find(fake(tags=[('v0.1.0', 't1')], releases=[('v0.1.0', False, False), ('v9.9.9', False, False)]), sources=['release'])
    assert [(v['version'], v['sha'], v['kinds']) for v in got['versions']] == [('0.1.0', 't1', ['release'])]

def test_drafts_skipped_prereleases_flagged_and_optionally_dropped():
    get = fake(tags=[('v1.0.0', 'a'), ('v1.1.0', 'b'), ('v1.2.0-RC1', 'c')], releases=[('v1.1.0', True, False), ('v1.0.0', False, True)])
    got, _ = find(get)
    assert [(v['version'], v['prerelease']) for v in got['versions']] == [('1.2.0-RC1', True), ('1.1.0', True), ('1.0.0', False)]
    assert got['versions'][2]['kinds'] == ['tag']  # the draft release does not count
    got, _ = find(get, include_prereleases=False)
    assert [v['version'] for v in got['versions']] == ['1.0.0']

def test_max_versions_caps_the_list_but_total_is_reported():
    got, _ = find(fake(tags=[(f'v1.0.{i}', str(i)) for i in range(7)]), max_versions=3)
    assert [v['version'] for v in got['versions']] == ['1.0.6', '1.0.5', '1.0.4'] and got['total'] == 7

def test_one_failing_source_does_not_lose_the_others():
    def get(path):
        if '/tags?' in path:
            raise RuntimeError('rate limited')
        return [{'ref': 'refs/heads/release-0.2.0', 'object': {'sha': 'b2'}}]
    got, logs = find(get)
    assert [v['version'] for v in got['versions']] == ['0.2.0'] and any('tag lookup failed' in l for l in logs)

def test_no_releases_gives_empty_list():
    got, _ = find(fake())
    assert got == {'versions': [], 'total': 0}
