import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from stackinfo.lookups import repostate as rs

def test_archived_repositories_are_marked_and_a_missing_guess_is_dropped(monkeypatch):
    monkeypatch.setattr(rs, 'STATE', {})
    monkeypatch.setattr(rs, 'TOPICS', {})
    asked = []
    def post(q):
        asked.append(q)
        return {'data': {'r0': {'isArchived': True, 'repositoryTopics': {'nodes': [{'topic': {'name': 's3'}}]}}, 'r1': None, 'r2': {'isArchived': False}}}   # sorted: minio, knowledge-provider-ui, sunbird
    deps = [{'ecosystem': 'docker', 'name': 'cgr.dev/chainguard/minio', 'project': 'github.com/minio/minio'},
            {'ecosystem': 'docker', 'name': 'ghcr.io/openagrinet/knowledge-provider-ui', 'project': 'github.com/openagrinet/knowledge-provider-ui',
             'project_of': 'same name', 'stars': 3, 'stars_of': 'x'},
            {'ecosystem': 'docker', 'name': 'ghcr.io/sunbird-rc/sunbird-rc-core', 'project': 'github.com/sunbird-rc/sunbird-rc-core', 'project_of': 'same name'}]
    rs.annotate(deps, post=post)
    assert len(asked) == 1 and 'isArchived' in asked[0] and 'repositoryTopics' in asked[0]
    assert rs.topics('Minio/Minio') == ['s3'] and rs.topics('sunbird-rc/sunbird-rc-core') == [] and rs.topics(None) == []
    assert deps[0]['archived'] is True
    assert 'project' not in deps[1] and 'stars' not in deps[1] and 'project_of' not in deps[1]   # no such repository
    assert deps[2]['project'] == 'github.com/sunbird-rc/sunbird-rc-core' and 'archived' not in deps[2] and 'project_of' not in deps[2]
    rs.annotate([{'ecosystem': 'docker', 'name': 'x', 'project': 'github.com/minio/minio'}], post=post)
    assert len(asked) == 1   # cached for the run

def test_a_failed_lookup_changes_nothing(monkeypatch):
    monkeypatch.setattr(rs, 'STATE', {})
    monkeypatch.setattr(rs, 'TOPICS', {})
    def post(q): raise RuntimeError('down')
    deps = [{'ecosystem': 'docker', 'name': 'x', 'project': 'github.com/o/r', 'project_of': 'same name'}]
    rs.annotate(deps, post=post, log=lambda m: None)
    assert deps[0]['project'] == 'github.com/o/r' and 'archived' not in deps[0]
