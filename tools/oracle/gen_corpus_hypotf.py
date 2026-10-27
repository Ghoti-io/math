#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned correctly-rounded binary32 hypotenuse references.

Rows: exact widened binary64 x/y/result words and a binary32 signed true-ULP
error word. Fraction squares/sums are converted exactly before directed
MPFR600 sqrt; independent mpmath640 must agree. Precision escalates rather
than guessing at either rounding boundary. Raw sNaNs are excluded because
widening quiets them; the raw unit/probe covers their priority and flags.
Expected values never read implementation source or private tables.
"""
import argparse
from pathlib import Path
import random
import tempfile
import gmpy2
import mpmath
from mpmath import mp
from gen_corpus_floattrig import (SIGN, INF, QNAN, Fraction, value, wide,
                                 power, fraction, round32, rational,
                                 mpmath_fraction, ulp_exp)

ONE = 0x3f800000
# Independent geometric witnesses: exact/subnormal Pythagorean roots, the
# subnormal-to-normal carry, and an exact overflow rounding midpoint.
# The final pair is the hardest reference-rounding case from seed20261027,
# count3000; its signed error rounds to the Float immediately above-.5.
# Further pairs exercise a low64 sum carry, both finite midpoint tie parities,
# and integer49990000^2+9999^2=49990001^2 (exactDouble/inexactFloat).
WITNESSES = ((3, 4), (1, 1), (0x007fffff, 0x00000fff),
             (0x7f6eccf8, 0x7eb8807f), (ONE, ONE),
             (INF - 1, 1), (INF - 1, INF - 1),
             (0x00ffffff, 0x00001000), (0x3fffffff, 0x3b800000),
             (0x4b7fffff, 0x46000000), (0x4a9ff14a, 0x4b896bb0),
             (round32(49990000), round32(9999)))


def signaling(raw):
    return (raw & ~SIGN) > INF and not raw & 0x00400000


def square_sum(x, y):
    return fraction(x) ** 2 + fraction(y) ** 2


def evaluate(x, y, precision):
    exact = square_sum(x, y)
    bounds = []
    for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
        with gmpy2.context(precision=precision, round=mode,
                          emin=gmpy2.get_emin_min(), emax=gmpy2.get_emax_max()):
            argument = gmpy2.mpfr(exact.numerator) / exact.denominator
            if rational(argument) != exact:
                return None
            bounds.append(rational(gmpy2.sqrt(argument)))
    low, high = bounds
    with mp.workprec(precision + 40):
        mx, my = mp.mpf(value(x)), mp.mpf(value(y))
        ms = mx * mx + my * my
        if mpmath_fraction(ms) != exact:
            return None
        independent = mpmath_fraction(mp.sqrt(ms))
    if abs(independent - (low + high) / 2) > high * power(-precision + 8):
        raise RuntimeError('MPFR/mpmath value disagreement: hypotf(%08x,%08x)' % (x, y))
    if not low or ulp_exp(low) != ulp_exp(high):
        return None
    result = round32(low)
    if result != round32(high) or result != round32(independent):
        return None
    if result == INF:
        return result, 0
    unit = power(ulp_exp(low))
    errors = [(v - fraction(result)) / unit for v in (low, high, independent)]
    error = round32(errors[0])
    if any(round32(v) != error for v in errors[1:]):
        return None
    # An exact Float root has zero error, certified against the original
    # rational sum rather than inferred from a rounded MPFR value.
    if fraction(result) ** 2 == exact:
        if low != fraction(result) or high != low or independent != low:
            raise RuntimeError('exact hypotenuse engine disagreement')
        return result, 0
    return result, error


def answer(x, y):
    a, b = x & ~SIGN, y & ~SIGN
    if signaling(x) or signaling(y):
        return QNAN, 0
    if a == INF or b == INF:
        return INF, 0
    if a > INF or b > INF:
        return QNAN, 0
    if not a:
        return b, 0
    if not b:
        return a, 0
    for precision in (600, 1200, 2400):
        result = evaluate(x, y, precision)
        if result is not None:
            return result
    raise RuntimeError('uncertified binary32 rounding boundary: hypotf(%08x,%08x)' % (x, y))


def require(condition, description):
    if not condition:
        raise RuntimeError('hypotf oracle self-check failed: ' + description)


def write_corpus(destination, population, seed, count, fresh, reference=answer):
    maximum, temporary = (Fraction(0), (0, 0)), None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent,
                                         prefix='.' + destination.name + '.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_hypotf.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function hypotf\n')
            out.write('# seed %d count %d fresh %s entries %d\n' % (seed, count, fresh, len(population)))
            out.write('# binary32 x/y/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for x, y in population:
                result, error = reference(x, y)
                out.write('%016x %016x %016x %08x\n' % (wide(x), wide(y), wide(result), error))
                if abs(fraction(error)) > maximum[0]:
                    maximum = abs(fraction(error)), (x, y)
        temporary.chmod(destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return maximum


def self_check():
    for x, y, result in ((0, SIGN, 0), (0, ONE | SIGN, ONE),
                         (INF, QNAN, INF), (QNAN | SIGN, INF | SIGN, INF),
                         (INF, INF | 1, QNAN), (INF | 1, INF, QNAN),
                         (QNAN, ONE, QNAN), (ONE, QNAN | SIGN, QNAN),
                         (3, 4, 5), (round32(3), round32(4), round32(5)),
                         (0x007fffff, 0x00000fff, 0x00800000),
                         (0x7f6eccf8, 0x7eb8807f, INF)):
        require(answer(x, y)[0] == result, 'special/geometric target')
    require(answer(3, 4) == (5, 0), 'exact subnormal Pythagorean root')
    require(answer(ONE, ONE) == (0x3fb504f3, 0x3e4fe77a),
            'sqrt2 actual rounded result and signed error')
    require(answer(1, 1) == (1, 0x3ed413cd), 'minimum-pair actual result/error')
    require(answer(0x007fffff, 0x00000fff) == (0x00800000, 0xb9fff000),
            'normal-carry actual negative signed error')
    require(answer(round32(3), round32(4)) == (round32(5), 0), 'exact normal Pythagorean root')
    require(square_sum(0x7f6eccf8, 0x7eb8807f) == (power(128) - power(103)) ** 2,
            'exact overflow midpoint geometry')
    for lower in (0, 1, 2, 0x007fffff, 0x00800000, 0x3f7fffff, ONE):
        midpoint = (fraction(lower) + fraction(lower + 1)) / 2
        require(round32(midpoint) == lower + (lower & 1), 'direct odd/even tie rounding')
    # First/second/late failures preserve absence or existing bytes and clean
    # temporary output; successful atomic publication preserves readable modes.
    for population, fail_at, existing in (([(0, 0)], (0, 0), False),
            ([(0, 0), (0, ONE)], (0, ONE), True),
            ([(0, 0), (0, ONE), (ONE, ONE)], (ONE, ONE), True)):
        with tempfile.TemporaryDirectory(prefix='hypotf-atomic-selfcheck-') as directory:
            destination = Path(directory) / 'hypotf.corpus'
            original = b'previous certified corpus\n'
            if existing:
                destination.write_bytes(original)
            def failure(x, y):
                if (x, y) == fail_at:
                    raise ArithmeticError('planted reference failure')
                return answer(x, y)
            try:
                write_corpus(destination, population, 1, 0, False, failure)
            except ArithmeticError:
                pass
            else:
                raise RuntimeError('hypotf oracle accepted planted failure')
            require(destination.read_bytes() == original if existing else not destination.exists(),
                    'failed publication preserves destination')
            require(list(Path(directory).iterdir()) == ([destination] if existing else []),
                    'failed publication cleans temporary file')
    for mode in (None, 0o640, 0o644):
        with tempfile.TemporaryDirectory(prefix='hypotf-mode-selfcheck-') as directory:
            destination = Path(directory) / 'hypotf.corpus'
            if mode is not None:
                destination.write_bytes(b'previous\n'); destination.chmod(mode)
            write_corpus(destination, [(0, 0)], 1, 0, False)
            require(destination.stat().st_mode & 0o777 == (0o644 if mode is None else mode),
                    'atomic readable permissions')


def inputs(seed, count, fresh):
    rng = random.Random(seed)
    seen, rows = set(), []
    def add(x, y):
        if not 0 <= x <= 0xffffffff or not 0 <= y <= 0xffffffff:
            return
        if signaling(x) or signaling(y) or (x, y) in seen:
            return
        seen.add((x, y)); rows.append((x, y))
    def symmetries(x, y):
        for sx in (0, SIGN):
            for sy in (0, SIGN):
                add(x | sx, y | sy); add(y | sy, x | sx)
    specials = (0, SIGN, 1, SIGN | 1, 0x007fffff, 0x00800000,
                ONE, ONE | SIGN, INF - 1, INF, INF | SIGN, QNAN, QNAN | SIGN | 7)
    for x in specials:
        for y in specials:
            add(x, y)
    for pair in WITNESSES:
        symmetries(*pair)
    for exponent in range(1, 255):
        a = (exponent << 23) | rng.getrandbits(23)
        for mantissa in (0, 1, 0x7fffff):
            symmetries((exponent << 23) | mantissa, a)
            symmetries((exponent << 23) | mantissa, 1)
    for length in range(1, 24):
        symmetries(1 << (length - 1), 1)
        for a in (1 << (length - 1), (1 << length) - 1):
            symmetries(a, rng.randrange(1, 1 << length))
    for a, b, c in ((3,4,5),(5,12,13),(7,24,25),(8,15,17),(20,21,29),(119,120,169)):
        for exponent in (-149,-148,-145,-130,-126,-20,0,20,100,120,121,124):
            x, y = round32(a * power(exponent)), round32(b * power(exponent))
            if x < INF and y < INF and fraction(x) == a*power(exponent) and fraction(y) == b*power(exponent):
                symmetries(x, y)
    for exponent in (-126,-10,0,100,127):
        for mantissa in (Fraction(1), Fraction(3,2), Fraction(2)-power(-23)):
            a = round32(mantissa * power(exponent))
            for gap in (12,13):
                b = round32(mantissa * power(exponent-gap))
                for delta in (-1,0,1):
                    if 0 < b+delta < INF:
                        symmetries(a,b+delta)
    for x,y in ((0x007fffff,0x00000fff),(0x7f6eccf8,0x7eb8807f)):
        for dx in range(-2,3):
            for dy in range(-2,3):
                symmetries(x+dx,y+dy)
    # Seek final-output midpoint decisions by exact circle geometry. Inverse
    # sqrt arguments are rational nonnegative and bounded by Float squares.
    with gmpy2.context(precision=600):
        for i in range(120 if fresh else 384):
            raw = rng.randrange(1, INF - 1)
            midpoint = (fraction(raw) + fraction(raw+1))/2
            x = round32(midpoint * Fraction(rng.randrange(1,8),8))
            remainder = midpoint*midpoint - fraction(x)**2
            if remainder <= 0:
                continue
            argument = gmpy2.mpfr(remainder.numerator)/remainder.denominator
            require(rational(argument) == remainder, 'exact inverse-circle argument')
            y = round32(rational(gmpy2.sqrt(argument)))
            for delta in (-2,-1,0,1,2):
                if 0 <= y+delta < INF:
                    symmetries(x,y+delta)
    for _ in range(count):
        add(rng.getrandbits(32),rng.getrandbits(32))
        add(round32(Fraction.from_float(rng.uniform(-1000,1000))),
            round32(Fraction.from_float(rng.uniform(-1000,1000))))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir','--out',dest='outdir',required=True,type=Path)
    parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--count',type=int,default=3000)
    parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    if args.count<0:parser.error('--count must be nonnegative')
    self_check()
    population=inputs(args.seed,args.count,args.fresh)
    args.outdir.mkdir(parents=True,exist_ok=True)
    maximum=write_corpus(args.outdir/'hypotf.corpus',population,args.seed,args.count,args.fresh)
    print('hypotf: %d entries; max reference error %.9g ULP at %08x,%08x' %
          (len(population),float(maximum[0]),*maximum[1]),flush=True)


if __name__=='__main__':main()
