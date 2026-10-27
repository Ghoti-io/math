#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory complete-file SHA256 of all exponent-reference payloads."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'logb-special.corpus': '20ae2d497a85031b40fa48338e8d8aa6520255cb9faf51df3848d62986523478', 'logbf-special.corpus': '31220599e219d3e0916e3fa505a5d1093897a104f1b5df3c947d9f6659c1287d', 'logb.corpus': '1678f75f3acb7bb992c6904ce703d9dfc60d19cf67d92a2f7f0967c459a7862d', 'logbf.corpus': '18f80f585003c71407688eca6e06b24a97ec1964f652e82f77b8f12881a61a35', 'exponent_value-special.hash': '0a48d30b14cb7dab78418bfc72426df447ce073c84a52bec3f4f1bcbc2f0c799'}
def main():
    if len(sys.argv)>2:raise RuntimeError('usage: check-exponent-value.py [DIRECTORY]')
    root=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,digest in EXPECTED.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('exponent payload checksum differs: '+name)
    print('exponent: five complete-file reference SHA256 values verified')
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError) as error:
        print('exponent reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
