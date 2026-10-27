#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require every byte of the committed exact Float scaling payloads."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'float_scale.corpus': '8464c9d6d5b400639bc7135f2843b496ad7fd57dbc76f1e2841b8d61cc2de6d8', 'scalbnf.corpus': 'f7fd3bae720c2d8444a3acca3757577175a9c5cc4c15d1a65a0592c89b79a29e', 'frexpf.corpus': '5490dc4333bb50d275c37c96b20652b08e60d405eeb375c283825b99aaaf380d', 'ilogbf.corpus': 'be0880385fd76cc040983e0f710c3e30b9cc1846de96610f420b59a2d72c6559', 'float_scale-special.hash': '3b58580cf127b1f8a5d1134d6099edbfc160424a9322c35de4c666633457a331'}

def main():
    if len(sys.argv)>2: raise RuntimeError('usage: check-floatscale-reference.py [corpus-directory]')
    directory=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,expected in EXPECTED.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('committed payload checksum differs: '+name)
    print('floatscale: complete committed payload SHA256 verified (five files)')
    return 0
if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,RuntimeError) as error:
        print('floatscale reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
