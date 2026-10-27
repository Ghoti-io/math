#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compare exact Float scaling output with committed result/state hashes."""
from pathlib import Path
import sys

def main():
    if len(sys.argv) not in (2,3):raise RuntimeError('usage: check-floatscale-output.py ACTUAL [CORPUS-DIR]')
    actual=Path(sys.argv[1]).read_bytes()
    directory=Path(sys.argv[2] if len(sys.argv)==3 else 'tests/corpus')
    if actual!=(directory/'float_scale-special.hash').read_bytes():raise RuntimeError('Float scale probe output differs')
    print(actual.decode('ascii'),end='')
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,UnicodeError) as error:
        print('floatscale output: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
