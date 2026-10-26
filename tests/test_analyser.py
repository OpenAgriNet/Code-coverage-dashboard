import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import analyser as a

def test_summarize_sorts_languages_and_dedupes_dependencies():
    raw = {'languages': {'YAML': 5, 'Go': 30, 'Markdown': 5}, 'techs': ['redis', 'golang', 'redis'],
           'dependencies': [['golang', 'github.com/b/x', 'v1.0.0'], ['docker', 'redis', 'alpine'], ['golang', 'github.com/b/x', 'v1.0.0']]}
    got = a.summarize(raw)
    assert got['languages'] == [('Go', 30), ('Markdown', 5), ('YAML', 5)]
    assert got['techs'] == ['golang', 'redis']
    assert got['dependencies'] == [['docker', 'redis', 'alpine'], ['golang', 'github.com/b/x', 'v1.0.0']]

def test_analyse_hides_tokens_from_git_and_npx(monkeypatch):
    for k in ('GH_TOKEN', 'DPG_PROJECT_TOKEN', 'CODECOV_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_URL'):
        monkeypatch.setenv(k, 'secret')
    envs = []
    def fake_run(cmd, **kw):
        envs.append(kw['env'])
        if cmd[0] == 'npx':
            open(os.path.join(kw['cwd'], 'out.json'), 'w').write('{}')
    monkeypatch.setattr(a.subprocess, 'run', fake_run)
    a.analyse('na', 'development')
    assert len(envs) == 2
    for env in envs:
        assert 'secret' not in env.values() and env['npm_config_ignore_scripts'] == 'true' and 'PATH' in env
