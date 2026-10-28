#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory complete-file checksums for native-long scaling references."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'scalbln-special.corpus': 'fefafa09ef8cb2f81e6889f686f7f914c0b9303f4c883bc61784774f21f66251', 'scalblnf-special.corpus': '26b99f0ec3ab023b13bb81f352bf7dea209e2a1ecb06ed396a9a6e127919e629', 'scalbln.corpus': '47387cebe9cbaa69ff419d5a85e29948237ca2f306e2e45ee5ddd0070b6089c8', 'scalblnf.corpus': 'ef2973641a9c4aceaa361525fff4ac875a3d009632d65684863f5fb997279a95', 'long_scale-special.hash': 'b51b6fe5ae3b69bab06082d0d4cf16bcb0dd53ceca23eb25c08331cbb4893ed9'}
def main():
    if len(sys.argv)>2:raise RuntimeError('usage: check-long-scale.py [DIRECTORY]')
    root=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,digest in EXPECTED.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('long scale payload checksum differs: '+name)
    print('long scale: five complete-file reference SHA256 values verified')
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError) as error:
        print('long scale reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
