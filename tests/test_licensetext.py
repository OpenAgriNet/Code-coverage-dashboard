from stackinfo.lookups import licensetext as lt

POSTGRES = '''PostgreSQL License
Permission to use, copy, modify, and distribute this software and its documentation for any purpose, without fee, and without a
written agreement is hereby granted, provided that the above copyright notice and this paragraph and the following two paragraphs
appear in all copies. IN NO EVENT SHALL THE UNIVERSITY OF CALIFORNIA BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL,
INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION.'''
MIT = '''Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.'''

def fake(texts):
    class R:
        def __init__(self, t): self.status_code, self.text = (200, t) if t else (404, '')
    return lambda url: R(texts.get(url.rsplit('/', 1)[1][:-4]))

def test_a_license_text_is_named_by_the_policy_license_it_matches(monkeypatch):
    monkeypatch.setattr(lt, 'TEXTS', {})
    monkeypatch.setattr(lt.settings, 'get', lambda k: ['PostgreSQL'])   # recognised, though on no policy list
    lt.use({'green': ['MIT', 'BSD-*'], 'red': ['non-standard']})
    get = fake({'MIT': MIT, 'PostgreSQL': POSTGRES})
    assert lt.candidates() == ['MIT', 'PostgreSQL', 'non-standard']   # patterns name no single text
    assert lt.identify('Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group\n' + POSTGRES, get=get) == 'PostgreSQL'
    assert lt.identify('All rights reserved. Do not copy.', get=get) is None
    assert lt.identify('', get=get) is None
