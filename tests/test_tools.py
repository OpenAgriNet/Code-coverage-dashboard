import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import tools as t

SECURITY = '''
jobs:
  scan:
    steps:
      - name: Install Trivy
        run: |
          curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b bin
      - run: pip install --upgrade pip-audit==2.7.3 -r requirements.txt bandit
'''
TEST = '''
      - run: python -m pip install pytest "pytest-cov>=5" -e .
      - run: npm install -g @redocly/cli@1.2.0 && npx --yes markdownlint-cli2 "**/*.md"
      - run: go install golang.org/x/vuln/cmd/govulncheck@v1.1.3
      - run: curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin v0.79.0
'''

def tree(tmp_path, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return str(tmp_path)

def test_tools_installed_in_workflows(tmp_path):
    src = tree(tmp_path, {'.github/workflows/security.yml': SECURITY, '.github/workflows/test.yml': TEST, 'deploy/compose.yml': 'pip install nope'})
    got = t.read(src)
    assert got[('githubRelease', 'aquasecurity/trivy')]['declared'] == 'latest' and got[('githubRelease', 'aquasecurity/trivy')]['groups'] == ['security']
    assert got[('githubRelease', 'anchore/grype')]['declared'] == 'v0.79.0' and got[('githubRelease', 'anchore/grype')]['groups'] == ['test']
    assert got[('python', 'pip-audit')]['declared'] == '==2.7.3' and got[('python', 'bandit')]['groups'] == ['security']
    assert got[('python', 'pytest')]['groups'] == ['test'] and got[('python', 'pytest-cov')]['declared'] == '>=5'
    assert got[('npm', '@redocly/cli')]['declared'] == '1.2.0' and got[('npm', 'markdownlint-cli2')]['groups'] == ['test']
    assert got[('golang', 'golang.org/x/vuln/cmd/govulncheck')]['declared'] == 'v1.1.3'
    assert ('python', 'requirements.txt') not in got and ('python', 'nope') not in got and ('python', '.') not in got

def test_purpose_from_the_workflow_name():
    assert [t.purpose(n) for n in ('security.yml', 'codeql.yml', 'run-tests.yml', 'lint.yml', 'build-and-push.yml', 'deploy.yml')] == \
        ['security', 'security', 'test', 'lint', 'build', 'ci']

def test_merge_keeps_both_groups():
    found = {('python', 'pytest'): {'name': 'pytest', 'declared': '>=9', 'installed': '9.1', 'groups': ['dev'], 'sources': ['pyproject.toml']}}
    tools = {('python', 'pytest'): {'name': 'pytest', 'declared': None, 'installed': None, 'groups': ['test'], 'sources': ['.github/workflows/test.yml']},
             ('githubRelease', 'aquasecurity/trivy'): {'name': 'aquasecurity/trivy', 'declared': 'latest', 'installed': None, 'groups': ['security'], 'sources': ['x']}}
    got = t.merge(found, tools)
    assert got[('python', 'pytest')]['groups'] == ['dev', 'test'] and got[('python', 'pytest')]['declared'] == '>=9'
    assert ('githubRelease', 'aquasecurity/trivy') in got
