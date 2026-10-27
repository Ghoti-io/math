#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require every byte of the committed exact integer-rounding payloads."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'intround64.corpus': '8c4c0b220fe1983cb97748087861c5d6be51bafe852c6492b4ed2c4592168a14', 'intround32.corpus': 'ab5271629c946ba9fb28130f140af0c6ffd617a2420895c8f35ab3279ae76444', 'lround.corpus': '638ad5879d5e261d2e336ae9ac4abbd715dbc1a589583ca13703427465269054', 'lroundf.corpus': 'ca812a63dd1948739fb12ec4a7dc9a6241e536faa3f13876939e61a03c8cabf6', 'intround-long32.hash': '69c3c2536e80a032c3987e4e72f85de6196a596e606bc0e3fee947f76d81a8eb', 'intround-long64.hash': '84824ef6a18c285255fda1ea73e4209956d947453f10424bc18062a190ded46a'}

def main():
    if len(sys.argv)>2: raise RuntimeError('usage: check-intround-reference.py [corpus-directory]')
    directory=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,expected in EXPECTED.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('committed payload checksum differs: '+name)
    print('intround: complete committed payload SHA256 verified (six files)')
    return 0
if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,RuntimeError) as error:
        print('intround reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
