#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Summarize the fixed host-comparison catalog; unequal is not incorrect.

Usage: audit-libm-compat.py results.csv
No runtime/gate contract changes, independent accuracy oracle, or speed claim.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

NAMES = set('sqrt floor ceil trunc round rint fabs lround llround nearbyint lrint llrint copysign scalbn ldexp scalbln frexp logb ilogb nextafter modf remainder remquo fmod fdim fmin fmax nan fma nexttoward sin cos tan exp exp2 cbrt log log2 log10 pow log1p expm1 asinh acosh atanh sinh cosh tanh asin acos atan atan2 hypot erf erfc tgamma lgamma'.split())
CASES = set('zero negative-zero half negative-one two minsub maxfinite infinity negative-infinity qnan-payload snan-payload one-and-half'.split())
FIELDS = 'name width case mode seed actual_seed ours host ours_aux host_aux ours_flags host_flags ours_errno host_errno ours_mode host_mode ours_signgam host_signgam'.split()

def summarize(path):
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError('unexpected CSV schema')
        rows = list(reader)
    expected = {(n, str(w), c, str(m), str(s)) for n in NAMES for w in (32, 64) for c in CASES for m in range(4) for s in range(2)}
    keys = [(r['name'], r['width'], r['case'], r['mode'], r['seed']) for r in rows]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError('missing, duplicate or unexpected comparison case')
    # Observe the platform's mode codes instead of assuming their encoding.
    modes = {m: {r['host_mode'] for r in rows if r['mode'] == str(m)} for m in range(4)}
    if any(len(codes) != 1 for codes in modes.values()) or len(set.union(*modes.values())) != 4:
        raise ValueError('host did not execute four distinct rounding modes')
    seeded = {int(r['actual_seed']) for r in rows if r['seed'] == '1'}
    if len(seeded) != 1 or not next(iter(seeded)):
        raise ValueError('incoming exception was not seeded consistently')
    for r in rows:
        for field in ('ours', 'host', 'ours_aux', 'host_aux'):
            word = r[field]
            if len(word) != 16 or any(c not in '0123456789abcdef' for c in word):
                raise ValueError('malformed result word')
        for field in FIELDS[10:] + ['actual_seed']:
            int(r[field])
        if r['seed'] == '0' and int(r['actual_seed']):
            raise ValueError('unexpected unseeded incoming flags')
        if (r['ours_mode'] != r['host_mode'] or int(r['ours_errno']) != 123
                or int(r['ours_flags']) & int(r['actual_seed']) != int(r['actual_seed'])
                or int(r['ours_signgam']) != 12345):
            raise ValueError('project caller-state contract failed in catalog')
    result = {'paired_cases': len(rows), 'entry_points': 114, 'project_state_failures': 0, 'difference_rows': {}}
    for axis in ('result', 'aux', 'flags', 'errno', 'signgam'):
        a, h = {'result': ('ours', 'host'), 'aux': ('ours_aux', 'host_aux')}.get(axis, ('ours_' + axis, 'host_' + axis))
        different = [r for r in rows if r[a] != r[h]]
        result['difference_rows'][axis] = {'rows': len(different), 'families': dict(sorted(Counter(r['name'] for r in different).items()))}
    result['interpretation'] = 'Fixed-catalog observations, not failure counts, exhaustive accuracy, standards conformance, or parity percentages.'
    return result

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: audit-libm-compat.py results.csv')
    print(json.dumps(summarize(Path(sys.argv[1])), indent=2))
