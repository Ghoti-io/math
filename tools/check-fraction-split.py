#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory complete-file SHA256 of all split-reference payloads."""
import hashlib
from pathlib import Path
import sys
EXPECTED = {'modf-special.corpus': '85944a7062a14417e890c2ac8018fcbfef94463e949912767492a965ef20c9dc', 'modf_fraction.corpus': 'ece6442c777ec75edac9e7cea29eaa937d7b8805b987dc60c7597cafff773f3b', 'modf_integral.corpus': '751193ee5067ca0fecc09b0af59c1d38ddad2ba20cc463b737846d974b719e93', 'modff-special.corpus': 'c6b114f09aaa82a288e674471098bf6112af34e9e1a3c081ee4e01db91a9aa9d', 'modff_fraction.corpus': '9c25a2f12e46092dbf654434645cbbc98e02a964ba5907ed746940420e7a657f', 'modff_integral.corpus': '96f5dd823851d1570accd042601ff07f0aec38f0168e4d14b4d2fb9811639bf9', 'fraction_split-special.hash': 'e69b40b05e4ad8b5e80f92cc61c3d84f08fe80056f9aa433e23ce424ae915927'}
def main():
    if len(sys.argv)>2:raise RuntimeError('usage: check-fraction-split.py [DIRECTORY]')
    root=Path(sys.argv[1] if len(sys.argv)==2 else 'tests/corpus')
    for name,digest in EXPECTED.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('split payload checksum differs: '+name)
    print('split: seven complete-file reference SHA256 values verified')
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError) as error:
        print('split reference: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
