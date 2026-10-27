#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compare actual native-width integer probe output to its committed contract."""
from pathlib import Path
import sys

def main():
    if len(sys.argv) not in (2,3):raise RuntimeError('usage: check-intround-output.py ACTUAL [CORPUS-DIR]')
    actual=Path(sys.argv[1]).read_bytes()
    first=actual.splitlines()[0] if actual else b''
    if first not in (b'math.intround_long.bits 32',b'math.intround_long.bits 64'):
        raise RuntimeError('missing/invalid native long width')
    bits=first.rsplit(b' ',1)[1].decode('ascii')
    directory=Path(sys.argv[2] if len(sys.argv)==3 else 'tests/corpus')
    if actual!=(directory/('intround-long'+bits+'.hash')).read_bytes():raise RuntimeError('integer probe output differs for native long'+bits)
    print(actual.decode('ascii'),end='')
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,UnicodeError) as error:
        print('intround output: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
