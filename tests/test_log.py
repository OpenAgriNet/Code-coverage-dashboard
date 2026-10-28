import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from stackinfo import log

def test_control_characters_never_reach_the_log(capsys):
    log.warn('WARN image x\n::add-mask::secret\r::stop-commands::t\x1b[31m')
    err = capsys.readouterr().err
    assert err.count('\n') == 1 and not any(line.startswith('::') for line in err.splitlines()) and '\x1b' not in err

def test_long_text_is_cut():
    assert len(log.clean('x' * 5000)) == 400
