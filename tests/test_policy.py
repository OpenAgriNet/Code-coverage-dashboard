import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from stackinfo.rules.policy import classify

P = {'green': ['MIT', 'Apache-2.0', 'BSD-*'], 'yellow': ['MPL-2.0', 'LGPL-*'], 'red': ['AGPL-*', 'GPL-*', 'SSPL-1.0']}

@pytest.mark.parametrize('expr,cls', [
    ('MIT', 'green'), ('mit', 'green'), ('BSD-3-Clause', 'green'), ('MPL-2.0', 'yellow'), ('LGPL-2.1-only', 'yellow'),
    ('GPL-3.0-only', 'red'), ('AGPL-3.0-or-later', 'red'), ('SSPL-1.0', 'red'), ('HPND', 'unclassified'), ('non-standard', 'unclassified'),
])
def test_single_license(expr, cls):
    assert classify(expr, P) == cls

def test_no_license_has_no_class():
    assert classify(None, P) is None and classify('', P) is None

def test_or_takes_the_better_choice_and_and_the_worse():
    assert classify('MIT OR GPL-3.0-only', P) == 'green'
    assert classify('GPL-2.0-only OR MPL-2.0', P) == 'yellow'
    assert classify('MIT AND GPL-3.0-only', P) == 'red'
    assert classify('(MIT AND Zlib)', P) == 'unclassified'
    assert classify('MIT OR Apache-2.0', P) == 'green'

def test_and_binds_tighter_than_or():
    assert classify('MIT OR GPL-3.0-only AND AGPL-3.0-only', P) == 'green'   # MIT OR (GPL AND AGPL)
    assert classify('GPL-3.0-only AND AGPL-3.0-only OR MPL-2.0', P) == 'yellow'

def test_parentheses_change_the_grouping():
    assert classify('(MIT OR GPL-3.0-only) AND AGPL-3.0-only', P) == 'red'   # the old splitter said green here
    assert classify('(MIT OR Apache-2.0) AND MPL-2.0', P) == 'yellow'
    assert classify('((MIT))', P) == 'green'

def test_several_licenses_listed_together_all_apply():
    assert classify('MIT, Apache-2.0', P) == 'green'
    assert classify('MIT, GPL-3.0-only', P) == 'red'
    assert classify('MIT,GPL-3.0-only', P) == 'red'

def test_a_comma_list_of_expressions_is_classified_item_by_item():
    q = {'green': ['MIT', 'Apache-2.0'], 'yellow': [], 'red': ['GPL-*', 'AGPL-*']}
    assert classify('GPL-3.0-or-later OR MIT, Apache-2.0', q) == 'green'    # (GPL OR MIT) AND Apache
    q2 = {'green': ['MIT'], 'yellow': [], 'red': ['GPL-*', 'Apache-2.0']}
    assert classify('GPL-3.0-or-later OR MIT, Apache-2.0', q2) == 'red'     # the old reading, GPL OR (MIT AND Apache), said green
    assert classify('Apache-2.0 OR BSD-3-Clause, MIT', P) == 'green'
    assert classify('MIT, , Apache-2.0', P) == 'unclassified'

def test_a_comma_inside_parentheses_is_not_understood():
    assert classify('(MIT, Apache-2.0) OR GPL-3.0-only', P) == 'unclassified'

def test_with_exception_uses_the_listed_exception_or_the_base_license():
    assert classify('GPL-2.0-only WITH Classpath-exception-2.0', P) == 'red'
    assert classify('GPL-2.0-only WITH Classpath-exception-2.0', {**P, 'yellow': P['yellow'] + ['GPL-2.0-only WITH Classpath-exception-2.0']}) == 'red'  # red pattern GPL-* also matches; most restrictive wins
    assert classify('GPL-2.0-only WITH Classpath-exception-2.0', {'green': [], 'yellow': ['GPL-2.0-only WITH Classpath-exception-2.0'], 'red': []}) == 'yellow'

@pytest.mark.parametrize('bad', ['(MIT', 'MIT)', 'MIT OR', 'AND MIT', 'MIT AND OR GPL-3.0-only', '()', 'MIT WITH', 'MIT Apache-2.0'])
def test_unparseable_expressions_are_unclassified_never_friendly(bad):
    assert classify(bad, P) == 'unclassified'

def test_lowercase_operators_are_not_operators():
    assert classify('MIT or GPL-3.0-only', P) == 'unclassified'

def test_overlapping_patterns_most_restrictive_wins():
    assert classify('LGPL-3.0-only', {'green': [], 'yellow': ['LGPL-*'], 'red': ['*GPL-3.0*']}) == 'red'

def test_empty_policy_leaves_everything_unclassified():
    assert classify('MIT', {}) == 'unclassified'
