import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from common import versions as v

def ver(version, published, default=False):
    return {'versionKey': {'version': version}, 'publishedAt': published, 'isDefault': default}

def test_clean_version():
    assert v.clean_version('^1.2.6') == '1.2.6'
    assert v.clean_version('>=2.0,<3') == '2.0'
    assert v.clean_version('v1.6.0') == 'v1.6.0'
    assert v.clean_version('latest') is None
    assert v.clean_version('${REGISTRY_IMAGE_TAG}') is None

def test_latest_stable_skips_prerelease_default():
    assert v.latest_stable([ver('0.28.1', '2024'), ver('0.29.0', '2025'), ver('1.0.0.dev6', '2026', True)]) == '0.29.0'
    assert v.latest_stable([ver('0.65b0', '2025'), ver('0.66.0b1', '2026', True)]) == '0.66.0b1'  # nothing stable: keep the default
    assert v.latest_stable([ver('v1.2.0', '2025', True), ver('v1.3.0-rc.1', '2026')]) == 'v1.2.0'
    assert v.latest_stable([ver('4.15.1', '2026', True)]) == '4.15.1'
