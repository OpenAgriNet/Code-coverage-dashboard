"""The dependency scan's settings: config/dependencies.json, validated by repoconfig.config. They are read when this module is
first imported, so tests and one-off runs use the same mappings as the nightly run; collect_stack.py applies them again from the
config it loaded. reset() goes back to the file, configure() replaces them for the rest of the run."""
import os
from repoconfig.config import load_dependencies
FILE=os.path.join(os.path.dirname(__file__),'..','..','config','dependencies.json')
CURRENT=load_dependencies(FILE)

def configure(settings):
 """Use these settings (an already validated dependencies block) for the rest of the run."""
 CURRENT.clear();CURRENT.update(settings)
def reset():
 """Back to config/dependencies.json."""
 configure(load_dependencies(FILE))
def get(*path):
 v=CURRENT
 for k in path:v=v[k]
 return v
def check(name):
 """Whether the check named in dependencies.checks (vulnerabilities, actions, images, terraform, workflow_tools, stars) is on."""
 return CURRENT['checks'][name]
