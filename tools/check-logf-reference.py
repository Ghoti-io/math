#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pin the complete committed logf reference payload, even without an oracle.

The expected digest was certified by byte-identical pinned regeneration.
Fresh independent samples have different digests and are checked separately.
An optional path supports mutation checks; it still requires the committed
payload, never an arbitrary caller-provided digest.
"""
import hashlib
from pathlib import Path
import sys

EXPECTED = 'a33135351ea5051b69e336d97609cc67ffb7a381c61a7f554eedecaf7e2b4915'


def main():
    if len(sys.argv) > 2:
        print('usage: check-logf-reference.py [committed-payload-path]', file=sys.stderr)
        return 2
    path = Path(sys.argv[1] if len(sys.argv) == 2 else 'tests/corpus/logf.corpus')
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        print('logf reference: cannot read payload: %s' % error, file=sys.stderr)
        return 1
    if actual != EXPECTED:
        print('logf reference: committed payload checksum differs', file=sys.stderr)
        return 1
    print('logf reference: complete committed payload SHA256 verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
