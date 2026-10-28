import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo.pipeline import collect

def run(targets, defaults, logs=None):
    calls = []
    def record(t, policy=None, stack=None):
        calls.append(t['branch'])
        return {'repository': t['name'], 'branch': t['branch'], 'policy': policy, 'stack': stack}
    def default(name):
        if isinstance(defaults[name], Exception):
            raise defaults[name]
        return defaults[name]
    got = collect(targets, policy='P', stack='S', record=record, default_branch=default, log=(logs if logs is not None else []).append)
    return got, calls

def test_repo_on_its_default_branch_is_analysed_once_and_listed_in_both():
    got, calls = run([{'name': 'a', 'branch': 'main'}], {'a': 'main'})
    assert calls == ['main'] and got['repositories'][0] is got['main'][0]

def test_repo_on_a_working_branch_is_analysed_on_both_branches():
    got, calls = run([{'name': 'na', 'branch': 'development'}], {'na': 'main'})
    assert calls == ['development', 'main']
    assert got['repositories'][0]['branch'] == 'development' and got['main'][0]['branch'] == 'main'
    assert got['main'][0]['policy'] == 'P' and got['main'][0]['stack'] == 'S'   # same settings on both

def test_default_branch_lookup_failure_reuses_the_working_branch_record():
    logs = []
    got, calls = run([{'name': 'a', 'branch': 'development'}], {'a': RuntimeError('502')}, logs)
    assert calls == ['development'] and got['main'][0] is got['repositories'][0] and any('default branch' in l for l in logs)

def test_order_follows_the_targets():
    got, _ = run([{'name': 'a', 'branch': 'x'}, {'name': 'b', 'branch': 'main'}], {'a': 'main', 'b': 'main'})
    assert [r['repository'] for r in got['repositories']] == ['a', 'b'] == [r['repository'] for r in got['main']]

def test_the_default_branch_record_is_labelled_default():
    got, _ = run([{'name': 'na', 'branch': 'development', 'branch_source': 'pattern'}], {'na': 'main'})
    assert got['repositories'][0]['branch'] == 'development' and got['main'][0]['branch'] == 'main'
