import pytest
from stackinfo.lookups import licensetext as lt

POSTGRES = '''PostgreSQL License
Permission to use, copy, modify, and distribute this software and its documentation for any purpose, without fee, and without a
written agreement is hereby granted, provided that the above copyright notice and this paragraph and the following two paragraphs
appear in all copies. IN NO EVENT SHALL THE UNIVERSITY OF CALIFORNIA BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL,
INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION.'''
MIT = '''Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.'''

SSPL = ' '.join(f'sspl{n}' for n in range(200))
AGPL = ' '.join(f'agpl{n}' for n in range(200))
GPL = ' '.join(f'agpl{n}' for n in range(170)) + ' ' + ' '.join(f'gpl{n}' for n in range(30))   # nearly the AGPL text
INDEX = {'licenses': [{'licenseId': 'PostgreSQL', 'name': 'PostgreSQL License'}, {'licenseId': 'MIT', 'name': 'MIT License'},
                      {'licenseId': 'SSPL-1.0', 'name': 'Server Side Public License, v 1'},
                      {'licenseId': 'AGPL-3.0-only', 'name': 'GNU Affero General Public License v3.0 only'},
                      {'licenseId': 'AGPL-3.0-or-later', 'name': 'GNU Affero General Public License v3.0 or later'},
                      {'licenseId': 'GPL-3.0-only', 'name': 'GNU General Public License v3.0 only'},
                      {'licenseId': 'AGPL-3.0', 'name': 'GNU Affero General Public License v3.0', 'isDeprecatedLicenseId': True}]}

def fake(texts):
    class R:
        def __init__(self, t): self.status_code, self.text = (200, t) if t else (404, '')
        def json(self): return INDEX
    return lambda url: R('index') if url == lt.INDEX else R(texts.get(url.rsplit('/', 1)[1][:-4]))

@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(lt, 'TEXTS', {})
    monkeypatch.setattr(lt, 'NAMES', [])

def test_a_license_text_is_named_by_the_license_it_matches():
    lt.use({'green': ['MIT', 'BSD-*'], 'red': ['non-standard']})
    get = fake({'MIT': MIT, 'PostgreSQL': POSTGRES})
    assert lt.candidates() == ['MIT', 'non-standard']   # patterns name no single text
    assert 'PostgreSQL' in lt.candidates(POSTGRES, get)    # the text names it, so it is a candidate, though on no policy list
    assert lt.identify('Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group\n' + POSTGRES, get=get) == 'PostgreSQL'
    assert lt.identify('All rights reserved. Do not copy.', get=get) is None
    assert lt.identify('', get=get) is None

def test_a_file_of_several_licenses_is_read_section_by_section():
    lt.use({'green': ['MIT']})
    get = fake({'SSPL-1.0': SSPL, 'AGPL-3.0-only': AGPL, 'AGPL-3.0-or-later': AGPL, 'GPL-3.0-only': GPL})
    rsal = ' '.join(f'rsal{n}' for n in range(200))
    text = ('Contributions are subject to the user\'s choice of the licenses below.\n\n'
            f'1. Redis Source Available License 2.0 (RSALv2) Agreement\n=========\n{rsal}\n\n'
            f'2. Server Side Public License (SSPL)\n=========\n{SSPL}\n\n'
            f'3. GNU AFFERO GENERAL PUBLIC LICENSE, Version 3, 19 Nov 2007\n=========\n{AGPL}\n')
    assert lt.identify(text, get=get) == 'LicenseRef-RSALv2 OR SSPL-1.0 OR AGPL-3.0-only'
    assert lt.identify(text.replace('choice', 'terms'), get=get) == 'LicenseRef-RSALv2 AND SSPL-1.0 AND AGPL-3.0-only'
    assert lt.identify(f'1. Ours (X)\n====\n{rsal}\n2. Theirs\n====\n{rsal}', get=get) is None   # no section is a known license
