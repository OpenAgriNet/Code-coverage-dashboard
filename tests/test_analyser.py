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

def test_summarize_skips_malformed_dependency_entries():
    raw = {'dependencies': [['npm', 'a', '1'], ['npm', 'broken'], None, 'x', ['npm', 'b', '2', 'extra']]}
    assert a.summarize(raw)['dependencies'] == [['npm', 'a', '1']]

STACK = {'ignore_languages': ['Markdown', 'yaml', 'JSON'], 'ignore_techs': ['github', 'Docker', 'python'], 'max_languages': 2, 'min_share': 0.1, 'max_techs': 3}

def test_main_stack_drops_markup_and_tooling_and_keeps_the_biggest_few():
    raw = {'languages': {'Python': 171, 'Markdown': 57, 'YAML': 23, 'JSON': 9, 'Go': 30, 'Shell': 2}, 'techs': ['github', 'docker', 'python', 'redis', 'fastapi', 'qdrant', 'zipkin']}
    got = a.summarize(raw, STACK)
    assert got['languages'] == [('Python', 171), ('Go', 30)]   # Shell (2 files) is under the minimum share
    assert got['techs'] == ['fastapi', 'qdrant', 'redis']   # sorted, ignored ones gone (compared ignoring case), capped at 3

def test_without_stack_settings_nothing_is_dropped():
    got = a.summarize({'languages': {'Markdown': 5, 'Go': 9}, 'techs': ['github']})
    assert got['languages'] == [('Go', 9), ('Markdown', 5)] and got['techs'] == ['github']

def test_a_repo_with_only_docs_has_an_empty_main_stack():
    assert a.summarize({'languages': {'Markdown': 1}, 'techs': []}, STACK)['languages'] == []

def test_stray_files_below_the_minimum_share_are_not_main_stack():
    raw = {'languages': {'Go': 310, 'AMPL': 1, 'JSONiq': 1, 'Markdown': 99}, 'techs': []}
    assert a.summarize(raw, STACK)['languages'] == [('Go', 310)]   # AMPL is a go.mod; Markdown is ignored and does not count toward the share

def test_share_is_of_the_remaining_code_files_and_the_boundary_counts():
    assert a.summarize({'languages': {'Python': 90, 'Go': 10}, 'techs': []}, STACK)['languages'] == [('Python', 90), ('Go', 10)]
    assert a.summarize({'languages': {'Python': 91, 'Go': 9}, 'techs': []}, STACK)['languages'] == [('Python', 91)]
    assert a.summarize({'languages': {'Python': 91, 'Go': 9}, 'techs': []}, {**STACK, 'min_share': 0})['languages'] == [('Python', 91), ('Go', 9)]
