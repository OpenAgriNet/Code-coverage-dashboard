import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.names import short_name, add_short

def test_short_names_keep_the_last_segment_and_major_versions():
    cases = [('golang', 'github.com/google/uuid', 'uuid'), ('golang', 'github.com/jackc/pgerrcode', 'pgerrcode'),
             ('golang', 'github.com/jackc/pgx/v5', 'pgx/v5'), ('golang', 'github.com/moby/moby/api', 'api'),
             ('golang', 'gopkg.in/yaml.v3', 'yaml.v3'), ('npm', '@tanstack/react-query', 'react-query'), ('npm', 'react', 'react'),
             ('python', 'fastapi', 'fastapi'), ('githubAction', 'actions/cache', 'cache'), ('githubAction', './.github/actions/x', './.github/actions/x'),
             ('docker', 'docker.langfuse.com/langfuse/langfuse', 'langfuse'), ('docker', 'postgres', 'postgres')]
    assert [short_name(e, n) for e, n, _ in cases] == [s for _, _, s in cases]

def test_add_short_keeps_the_full_name():
    deps = [{'ecosystem': 'golang', 'name': 'github.com/jackc/pgx/v5'}]
    add_short(deps)
    assert deps == [{'ecosystem': 'golang', 'name': 'github.com/jackc/pgx/v5', 'short': 'pgx/v5'}]
