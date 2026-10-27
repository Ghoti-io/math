#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Unary Float arctangent references from directed MPFR and independent mpmath.

The evaluator is shared with atan2f, with exact positive abscissa one. No
candidate source or tables enter reference generation. Atomic publication
preserves an existing file's permissions and leaves previous data on failure.
"""
import argparse
from pathlib import Path
import random
import tempfile
from mpmath import mp
import gmpy2
import mpmath
from gen_corpus_atan2f import answer, ONE, SIGN, INF, signaling
from gen_corpus_floattrig import Fraction, fraction, power, round32, wide, mpmath_fraction


def inputs(seed, count):
    rng = random.Random(seed)
    words = {0, SIGN, INF, SIGN | INF, 0x7fc00000, 0xffc00007}
    def add(raw):
        if 0 <= raw < INF:
            words.update((raw, raw | SIGN))
    for exponent in range(255):
        for mantissa in (0, 1, 0x3fffff, 0x7ffffe, 0x7fffff):
            add((exponent << 23) | mantissa)
    for bit in range(23):
        for delta in (-1, 0, 1): add((1 << bit) + delta)
    for center in (0x30800000, 0x3e000000, ONE):
        for delta in range(-8, 9): add(center + delta)
    for j in range(8, 65):
        for q in (Fraction(j, 64), Fraction(2*j+1, 128)):
            for v in (q, 1/q):
                raw = round32(v)
                for delta in (-2, -1, 0, 1, 2): add(raw + delta)
    # Invert unary output midpoints, including reflected angles above pi/4.
    with mp.workprec(1240):
        strata = (("tiny", Fraction(1, 1 << 120), Fraction(1, 1 << 30)),
                  ("direct", Fraction(1, 1 << 10), Fraction(1, 8)),
                  ("table", Fraction(1, 8), Fraction(3, 4)),
                  ("reflected", Fraction(4, 5), Fraction(31, 20)))
        for label, low, high in strata:
            candidates = set()
            for i in range(128):
                target = low + (high-low)*Fraction(2*i+1,256)
                raw = round32(target)
                midpoint = (fraction(raw)+fraction(raw+1))/2
                inverse = mp.tan(mp.mpf(midpoint.numerator)/midpoint.denominator)
                center = round32(mpmath_fraction(inverse))
                for delta in (-1,0,1):
                    if 0 < center+delta < INF: add(center+delta);candidates.add(center+delta)
            if len(candidates) < 300: raise RuntimeError('insufficient '+label+' inverse candidates')
        # The final sixteen midpoint cells below true pi/2 stress reflection.
        endpoint = set()
        for raw in range(0x3fc90fcb,0x3fc90fdb):
            midpoint=(fraction(raw)+fraction(raw+1))/2
            inverse=mp.tan(mp.mpf(midpoint.numerator)/midpoint.denominator)
            center=round32(mpmath_fraction(inverse))
            for delta in (-1,0,1): add(center+delta);endpoint.add(center+delta)
        if len(endpoint)<40: raise RuntimeError('insufficient endpoint inverse candidates')
    for i in range(count):
        raw = rng.getrandbits(32)
        if not signaling(raw): words.add(raw)
    return sorted(words)


def publish(path, population, seed, count, fresh, reference=answer):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent,
                                         prefix='.'+path.name+'.', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_atanf.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function atanf\n# seed %d count %d fresh %s entries %d\n' %
                      (seed, count, fresh, len(population)))
            out.write('# binary32 input/result widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for raw in population:
                result, error = reference(raw, ONE)
                out.write('%016x %016x %08x\n' % (wide(raw), wide(result), error))
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        temporary.replace(path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def publication_self_check():
    for exists in (False, True):
        for position in (0,1,2):
            with tempfile.TemporaryDirectory(prefix='atanf-publish-') as directory:
                path=Path(directory)/'atanf.corpus'
                if exists: path.write_bytes(b'previous\n');path.chmod(0o640)
                calls=0
                def broken(raw, one):
                    nonlocal calls
                    calls+=1
                    if calls==position+1: raise RuntimeError('injected reference failure')
                    return answer(raw,one)
                try: publish(path,[0,ONE,INF],1,0,False,broken)
                except RuntimeError as error:
                    if str(error)!='injected reference failure': raise
                else: raise RuntimeError('publication failure escaped')
                if exists:
                    if path.read_bytes()!=b'previous\n' or path.stat().st_mode&0o777!=0o640:
                        raise RuntimeError('failed publication changed destination')
                elif path.exists(): raise RuntimeError('failed publication created destination')
                if list(Path(directory).glob('.atanf.corpus.*')): raise RuntimeError('temporary file leaked')
    for mode in (None,0o640,0o644):
        with tempfile.TemporaryDirectory(prefix='atanf-mode-') as directory:
            path=Path(directory)/'atanf.corpus'
            if mode is not None: path.write_bytes(b'previous');path.chmod(mode)
            publish(path,[0],1,0,False)
            if path.stat().st_mode&0o777 != (0o644 if mode is None else mode):
                raise RuntimeError('publication mode changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=20261027)
    parser.add_argument('--count', type=int, default=5000)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.count <= 10000000: parser.error('--count must be in 0..10000000')
    if not 0 <= args.seed < 1 << 64: parser.error('--seed must be an unsigned 64-bit integer')
    # Direct unary calls cross-check the shared atan2 evaluator independently.
    with gmpy2.context(precision=1200):
        for raw in (1, 0x00800000, 0x30800000, 0x3e000000, ONE, INF-1):
            from gen_corpus_floattrig import value, rational
            expected = round32(rational(gmpy2.atan(gmpy2.mpfr(value(raw)))))
            if answer(raw, ONE)[0] != expected: raise RuntimeError('unary atan self-check failed')
    publication_self_check()
    population = inputs(args.seed, args.count)
    args.out.mkdir(parents=True, exist_ok=True)
    publish(args.out/'atanf.corpus', population, args.seed, args.count, args.fresh)
    print('atanf: %d certified entries' % len(population), flush=True)


if __name__ == '__main__': main()
