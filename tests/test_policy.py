import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import pytest
from stackinfo.policy import classify

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

def test_overlapping_patterns_most_restrictive_wins():
    assert classify('LGPL-3.0-only', {'green': [], 'yellow': ['LGPL-*'], 'red': ['*GPL-3.0*']}) == 'red'

def test_empty_policy_leaves_everything_unclassified():
    assert classify('MIT', {}) == 'unclassified'
