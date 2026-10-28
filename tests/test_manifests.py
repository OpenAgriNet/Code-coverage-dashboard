import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.sources import manifests as m

def tree(tmp_path, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else json.dumps(text))
    return str(tmp_path)

def test_npm_groups_and_installed_versions(tmp_path):
    src = tree(tmp_path, {
        'ui/package.json': {'dependencies': {'react': '^18.2.0'}, 'devDependencies': {'vite': '^5.0.0', 'react': '^18.2.0'},
                            'optionalDependencies': {'fsevents': '*'}, 'peerDependencies': {'react-dom': '>=18'}},
        'ui/package-lock.json': {'packages': {'': {}, 'node_modules/react': {'version': '18.3.1'}, 'node_modules/vite': {'version': '5.4.2'},
                                              'node_modules/vite/node_modules/esbuild': {'version': '0.21.5'}}},
        'node_modules/x/package.json': {'dependencies': {'leftpad': '1'}}})
    got = m.read(src)
    assert got[('npm', 'react')] == {'name': 'react', 'declared': '^18.2.0', 'groups': ['dev', 'main'], 'installed': '18.3.1', 'sources': ['ui/package.json']}
    assert got[('npm', 'vite')]['groups'] == ['dev'] and got[('npm', 'vite')]['installed'] == '5.4.2'
    assert got[('npm', 'fsevents')]['groups'] == ['optional'] and got[('npm', 'react-dom')]['groups'] == ['peer']
    assert ('npm', 'leftpad') not in got and ('npm', 'esbuild') not in got

def test_pyproject_groups_named_by_the_repo(tmp_path):
    src = tree(tmp_path, {'pyproject.toml': '''
[project]
dependencies = ["FastAPI>=0.110", "pydantic[email]==2.7.1 ; python_version>'3.9'"]
[project.optional-dependencies]
security = ["bandit"]
[dependency-groups]
dev = ["pytest>=8", {include-group = "lint"}]
tests = ["httpx"]
lint = ["ruff"]
''', 'uv.lock': '''
[[package]]
name = "fastapi"
version = "0.115.2"

[[package]]
name = "starlette"
version = "0.41.0"
'''})
    got = m.read(src)
    assert got[('python', 'fastapi')] == {'name': 'FastAPI', 'declared': '>=0.110', 'groups': ['main'], 'installed': '0.115.2', 'sources': ['pyproject.toml']}
    assert got[('python', 'pydantic')]['groups'] == ['main'] and got[('python', 'pydantic')]['installed'] is None
    assert got[('python', 'bandit')]['groups'] == ['security'] and got[('python', 'pytest')]['groups'] == ['dev']
    assert got[('python', 'httpx')]['groups'] == ['test'] and got[('python', 'ruff')]['groups'] == ['lint']
    assert ('python', 'starlette') not in got

def test_poetry_groups(tmp_path):
    src = tree(tmp_path, {'pyproject.toml': '''
[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.31"
[tool.poetry.dev-dependencies]
black = "*"
[tool.poetry.group.testing.dependencies]
pytest-cov = "*"
''', 'poetry.lock': '[[package]]\nname = "requests"\nversion = "2.32.3"\n'})
    got = m.read(src)
    assert ('python', 'python') not in got
    assert got[('python', 'requests')]['groups'] == ['main'] and got[('python', 'requests')]['installed'] == '2.32.3'
    assert got[('python', 'black')]['groups'] == ['dev'] and got[('python', 'pytest-cov')]['groups'] == ['test']

def test_requirements_files_name_their_group(tmp_path):
    src = tree(tmp_path, {'requirements.txt': '# app\nDjango==5.0.1\n-r requirements-dev.txt\n-e .\n',
                          'requirements-dev.txt': 'pytest\n', 'requirements/prod.txt': 'gunicorn>=21\n', 'requirements/base.txt': 'celery\n',
                          'requirements_security.txt': 'pip-audit  # scanner\n'})
    got = m.read(src)
    assert got[('python', 'django')]['groups'] == ['main'] and got[('python', 'celery')]['groups'] == ['main']
    assert got[('python', 'pytest')]['groups'] == ['dev'] and got[('python', 'gunicorn')]['groups'] == ['prod']
    assert got[('python', 'pip-audit')]['groups'] == ['security']

def test_go_mod_direct_and_tools(tmp_path):
    src = tree(tmp_path, {'go.mod': 'module x\n\nrequire (\n\tgithub.com/a/b v1.2.0\n\tgithub.com/c/d v0.1.0 // indirect\n)\nrequire github.com/e/f v2.0.0\ntool golang.org/x/tools/cmd/stringer\n'})
    got = m.read(src)
    assert got[('golang', 'github.com/a/b')]['groups'] == ['main'] and got[('golang', 'github.com/e/f')]['groups'] == ['main']
    assert got[('golang', 'golang.org/x/tools/cmd/stringer')]['groups'] == ['tool'] and ('golang', 'github.com/c/d') not in got

def test_broken_files_are_skipped(tmp_path):
    src = tree(tmp_path, {'package.json': '{not json', 'pyproject.toml': '[[[', 'go.mod': 'require'})
    assert m.read(src) == {}

def test_group_names_are_normalised_only_for_spelling():
    assert [m.group_name(g) for g in ('tests', 'Testing', 'develop', 'development', 'Security', 'docs')] == ['test', 'test', 'dev', 'dev', 'security', 'docs']

def test_attach_labels_rows_and_prefers_installed_for_ranges():
    deps = [{'ecosystem': 'npm', 'name': 'react', 'version': '^18.2.0'}, {'ecosystem': 'python', 'name': 'FastAPI', 'version': '0.110'},
            {'ecosystem': 'docker', 'name': 'postgres', 'version': '17'}, {'ecosystem': 'githubAction', 'name': 'actions/cache', 'version': 'v4'},
            {'ecosystem': 'npm', 'name': 'unknown', 'version': '1.0.0'}]
    found = {('npm', 'react'): {'groups': ['main'], 'installed': '18.3.1', 'sources': ['package.json']},
             ('python', 'fastapi'): {'groups': ['main'], 'installed': '0.110', 'sources': ['pyproject.toml']}}
    m.attach(deps, found)
    assert deps[0]['groups'] == ['main'] and deps[0]['installed'] == '18.3.1' and deps[0]['sources'] == ['package.json']
    assert deps[1]['groups'] == ['main'] and 'installed' not in deps[1]   # already exact: nothing to add
    assert deps[2]['groups'] == ['runtime'] and deps[3]['groups'] == ['ci'] and deps[4]['groups'] == []

def test_build_requirements_and_declared_versions(tmp_path):
    src = tree(tmp_path, {'pyproject.toml': '[build-system]\nrequires = ["hatchling>=1.32.0"]\n[dependency-groups]\ndev = ["pytest>=9.1.1", "ruff"]\n'})
    got = m.read(src)
    assert got[('python', 'hatchling')]['groups'] == ['build'] and got[('python', 'hatchling')]['declared'] == '>=1.32.0'
    assert got[('python', 'pytest')]['declared'] == '>=9.1.1' and got[('python', 'ruff')]['declared'] is None

def test_unlisted_adds_what_the_analyser_missed():
    found = {('python', 'pytest'): {'name': 'pytest', 'declared': '>=9.1.1', 'installed': '9.1.2', 'groups': ['dev'], 'sources': ['pyproject.toml']},
             ('python', 'ruff'): {'name': 'ruff', 'declared': None, 'installed': '0.16.4', 'groups': ['dev'], 'sources': ['pyproject.toml']},
             ('python', 'fastapi'): {'name': 'FastAPI', 'declared': '>=0.1', 'installed': None, 'groups': ['main'], 'sources': ['pyproject.toml']},
             ('python', 'en-core-web-sm'): {'name': 'en-core-web-sm', 'declared': None, 'installed': None, 'groups': ['main'], 'sources': ['pyproject.toml']}}
    rows = [['python', 'fastapi', '0.1'], ['python', 'en_core_web_sm', 'latest']]
    assert m.unlisted(found, rows) == [['python', 'pytest', '>=9.1.1'], ['python', 'ruff', '0.16.4']]
