"""The dependency scan's settings: config/repos.json's "dependencies" block, validated by repoconfig.config over its defaults.
collect_stack.py calls configure() once with the loaded config; until then (tests, one-off runs) the defaults apply."""
from repoconfig.config import dependency_settings
CURRENT=dependency_settings(None)

def configure(settings):
 """Use these settings (an already validated "dependencies" block) for the rest of the run."""
 CURRENT.clear();CURRENT.update(settings)
def get(*path):
 v=CURRENT
 for k in path:v=v[k]
 return v
def check(name):
 """Whether the check named in dependencies.checks (vulnerabilities, actions, images, terraform, workflow_tools, stars) is on."""
 return CURRENT['checks'][name]
