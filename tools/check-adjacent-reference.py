#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require every byte of the committed exact adjacent-value payloads."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'nextafter-special.corpus': '5d0c1aa0cf6e47d23238043e1ac42581d5e70a25c6167c6607153d329131f09c', 'nextafterf-special.corpus': '04403c6b7d9d73a5470d10fbc3e3d9c4a50474108eed56a2bbcd358fd3000425', 'nextafter.corpus': 'bee3f143ff1f8729aca677e62139b5350027c22297020bf10265c19c86db882e', 'nextafterf.corpus': 'f5964f19ac5ecce69d9fc4b49df980af3824e0d5382fffef8d765616075084b0', 'adjacent-special.hash': '6b2bb6a7af4c83661f5a14a5932ef34597c3093b7e9d5b2da26081cfc81c3461'}

def main():
    if len(sys.argv)>2: raise RuntimeError('usage: check-adjacent-reference.py [corpus-directory]')
    directory=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,expected in EXPECTED.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('committed payload checksum differs: '+name)
    print('adjacent: complete committed payload SHA256 verified (five files)')
    return 0
if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,RuntimeError) as error:
        print('adjacent reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
