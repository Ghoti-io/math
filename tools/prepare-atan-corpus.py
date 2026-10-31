#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Materialize pinned arctangent grids without a container.

Seeded answers remain literal committed inputs. Deterministic rows use Decimal
half-angle reduction and an alternating series, then must reproduce the entire
independently MPFR/mpmath-certified byte streams. This is cache reconstruction,
not an additional transcendental accuracy proof. Corrupt caches fail closed.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import os
from pathlib import Path
import random
import tempfile
from atan_reference import (COUNT, SEED, SIGN, INF, QNAN, power, fraction,
                            floor_log2, round_word, flags, population)

EXPECTED = {
    'atan-special.corpus': '4536e60e605ae4adf349928c1946ad20aade18a34209ac0f6f2bc852318f694e',
    'atan.corpus': 'd5605413f8faf933c8239e9e56f5e087fab54297d7ff6abdb4926ba1d60388fb',
}
SEED_SHA = '0bf1c314241e22e767b83a7d0a43bf7dc9d99ea3fba7bdcb3b4a8e436e7be0ec'
PROVENANCE = '# Pinned oracle: atan MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1'
HEADER = PROVENANCE + '\n# function %s\n# seed 20261028 count 2000 fresh false entries %d\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    maximum = 8*1024*1024
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise RuntimeError('atan cache file missing/nonregular/oversized: '+str(path))
    with path.open('rb') as stream:
        data = stream.read(maximum+1)
    if len(data) > maximum:
        raise RuntimeError('atan cache file grew beyond bound: '+str(path))
    return data


def series(x):
    term = total = x
    square = -x*x
    for n in range(1, 1000):
        term *= square
        previous = total
        total += term/(2*n+1)
        if total == previous:
            return total
    raise RuntimeError('atan cache series failed to converge')


def answer(raw, pi):
    a = raw & (SIGN-1)
    if a > INF:
        return QNAN, 0
    if not a:
        return raw, 0
    if a < 0x3970000000000000:  # |x|<2^-104: certified signed-error-zero bound.
        return raw, 0 if raw & SIGN else 0x80000000
    if a == INF:
        value = pi/2
    else:
        q = abs(fraction(raw))
        x = Decimal(q.numerator)/Decimal(q.denominator)
        invert = x > 1
        if invert:
            x = 1/x
        scale = 1
        while x > Decimal('0.125'):
            x = x/(1+(1+x*x).sqrt())
            scale *= 2
        value = scale*series(x)
        if invert:
            value = pi/2-value
    if raw & SIGN:
        value = -value
    value = Fraction(value)
    target = round_word(value)
    unit = power(max(floor_log2(value), -1022)-52)
    return target, round_word((value-fraction(target))/unit, 32)


def seeds(directory):
    data = read(directory/'atan-seeded.corpus')
    if sha(data) != SEED_SHA:
        raise RuntimeError('atan seeded answers SHA256 differs')
    lines = data.decode('ascii').splitlines()
    expected = [PROVENANCE, '# function atan64-seeded',
                '# seed 20261028 count 2000 fresh false entries 2000',
                '# input nearest-target signed-error32 normalized-flags']
    if lines[:4] != expected:
        raise RuntimeError('atan seeded schema differs')
    rows = [tuple(int(word, 16 if n < 3 else 10)
                  for n, word in enumerate(line.split())) for line in lines[4:]]
    rng = random.Random(SEED)
    words = sorted({rng.getrandbits(64) for _ in range(COUNT)})
    if [row[0] for row in rows] != words or any(len(row) != 4 for row in rows):
        raise RuntimeError('atan seeded population differs')
    return {row[0]: row for row in rows}


def payloads(seed_rows, precision=170):
    with localcontext() as context:
        context.prec = precision
        pi = 16*series(Decimal(1)/5)-4*series(Decimal(1)/239)
        rows = []
        for word in population(SEED, COUNT):
            if word in seed_rows:
                row = seed_rows[word]
            else:
                target, error = answer(word, pi)
                row = word, target, error, flags(word)
            rows.append(row)
    generic = [r for r in rows if not ((r[0] & (SIGN-1)) > INF and not r[0] & (1 << 51))]
    return {
        'atan-special.corpus': (HEADER % ('atan64', len(rows)) +
            '# input nearest-target signed-error32 normalized-flags\n' +
            ''.join('%016x %016x %08x %d\n' % r for r in rows)).encode('ascii'),
        'atan.corpus': (HEADER % ('atan', len(generic)) +
            '# binary64 input/result; signed binary32 error in true binary64 ULP\n' +
            ''.join('%016x %016x %08x\n' % r[:3] for r in generic)).encode('ascii'),
    }


def prepare(directory, verify_only=False):
    seed_rows = seeds(directory)
    missing = []
    for name, expected in EXPECTED.items():
        path = directory/name
        if path.exists() or path.is_symlink():
            if sha(read(path)) != expected:
                raise RuntimeError('atan existing cache SHA256 differs: '+name)
        else:
            missing.append(name)
    if not missing:
        return
    if verify_only:
        raise RuntimeError('atan cache missing: '+', '.join(missing))
    data = payloads(seed_rows)
    for name, expected in EXPECTED.items():
        if sha(data[name]) != expected:
            raise RuntimeError('atan reconstructed pinned SHA256 differs: '+name)
    # Publish only missing, fully certified files. A partial publication is
    # recoverable on the next invocation; this is not a multi-file transaction.
    for name in missing:
        path = directory/name
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix='.atan-cache-', delete=False) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), 0o644)
                stream.write(data[name])
            try:
                # Atomic no-replace publication: another invocation may have
                # created the destination after the initial existence check.
                os.link(temporary, path)
            except FileExistsError:
                if sha(read(path)) != EXPECTED[name]:
                    raise RuntimeError('atan cache changed during publication: '+name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('tests/corpus'))
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    prepare(args.directory, args.verify_only)
    print('atan pinned grid cache and literal seeded answers verified')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit('atan cache: FAIL: '+str(error))
