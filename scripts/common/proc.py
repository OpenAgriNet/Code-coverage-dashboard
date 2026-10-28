"""Environment for child processes (git, npx, docker, osv-scanner)."""
import os
SAFE_ENV=('PATH','HOME','TMPDIR','TEMP','TMP','LANG','LC_ALL','XDG_CACHE_HOME','RUNNER_TEMP')

def child_env():
 """Environment for git and npx: an allowlist, so third-party npm code never sees GH_TOKEN, DPG_PROJECT_TOKEN or the Actions OIDC request token."""
 env={k:os.environ[k] for k in SAFE_ENV if k in os.environ}
 env.update(npm_config_ignore_scripts='true',GIT_TERMINAL_PROMPT='0')
 return env
