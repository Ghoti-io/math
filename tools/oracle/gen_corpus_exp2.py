#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned MPFR600/mpmath640 oracle for exp2; x_bits r_bits signed_err_bits.

Rational rounding handles the subnormal grid, ties to zero and overflow. The
signed error uses spacing at the true value, including the subnormal grid.
Run through tools/oracle/oracle.py exp2|fresh-exp2, never a host oracle.
"""
import argparse
from fractions import Fraction
import math
from pathlib import Path
import random
import struct

import gmpy2
import mpmath
from mpmath import mp

SIGN = 0x8000000000000000
INF = 0x7ff0000000000000
QNAN = 0x7ff8000000000000
OVER = Fraction(2) ** 1024 - Fraction(2) ** 970
HALF_MIN = Fraction(2) ** -1075


def bits(x):
    return struct.unpack('>Q', struct.pack('>d', x))[0]


def value(u):
    return struct.unpack('>d', struct.pack('>Q', u))[0]


def exponent(a):
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if a < Fraction(2) ** e:
        e -= 1
    return e


def rounded(fr):
    if fr >= OVER:
        return INF, 0
    if fr <= HALF_MIN:
        return 0, 0
    unit = Fraction(2) ** (max(exponent(fr), -1022) - 52)
    scaled = fr / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r > scaled.denominator or (2 * r == scaled.denominator and q & 1):
        q += 1
    exact_rounded = q * unit
    result = float(exact_rounded)
    if Fraction.from_float(result) != exact_rounded:
        raise RuntimeError('exp2 oracle target rounding was not exact')
    error = (fr - exact_rounded) / unit
    ebits = struct.unpack('>I', struct.pack('>f', float(error)))[0]
    return bits(result), ebits


def entry(xb):
    x = value(xb)
    a = xb & ~SIGN
    if a > INF:
        return QNAN, 0
    if a == INF:
        return (0 if xb & SIGN else INF), 0
    if a == 0:
        return bits(1.0), 0
    # These exact inequalities avoid attempting enormous exp2 computations.
    # Nearby finite thresholds are still evaluated by both independent tools.
    if x > 1025:
        return INF, 0
    if x < -1076:
        return 0, 0
    with gmpy2.context(precision=600, emin=gmpy2.get_emin_min(),
                      emax=gmpy2.get_emax_max()):
        reference = gmpy2.exp2(gmpy2.mpfr(x))
    n, d = reference.as_integer_ratio()
    fr = Fraction(int(n), int(d))
    mp.prec = 640
    independent = mp.power(2, mp.mpf(x))
    as_mp = mp.mpf(fr.numerator) / mp.mpf(fr.denominator)
    if abs(independent - as_mp) > abs(as_mp) * mp.mpf(2) ** -400:
        raise RuntimeError('MPFR and mpmath disagree for exp2(%016x)' % xb)
    # Convert the independent mpmath value through its public arithmetic API,
    # then round it separately: relative agreement alone cannot settle a result
    # whose exact value lies exceptionally close to a rounding midpoint.
    mantissa, power = mp.frexp(independent)
    significant = int(mp.ldexp(mantissa, mp.prec))
    independent_fraction = Fraction(significant) * Fraction(2) ** (int(power) - mp.prec)
    result = rounded(fr)
    independent_result = rounded(independent_fraction)
    if result[0] != independent_result[0]:
        raise RuntimeError('MPFR and mpmath rounded exp2 results disagree for %016x' % xb)
    if x >= 1024 and result[0] != INF:
        raise RuntimeError('exp2 oracle overflow threshold disagrees with MPFR')
    if x <= -1075 and result[0] != 0:
        raise RuntimeError('exp2 oracle zero threshold disagrees with MPFR')
    return result


def self_check():
    for xb, expected in ((SIGN, bits(1.0)), (INF, INF), (INF | SIGN, 0),
                         (QNAN | 7, QNAN), (INF | 1, QNAN)):
        if entry(xb) != (expected, 0):
            raise RuntimeError('exp2 oracle self-check failed: IEEE special value')
    for x, expected in ((-1075.0, 0), (-1074.0, 1),
                        (-1022.0, 0x0010000000000000),
                        (-1.0, 0x3fe0000000000000),
                        (0.0, 0x3ff0000000000000),
                        (1.0, 0x4000000000000000),
                        (1023.0, 0x7fe0000000000000), (1024.0, INF)):
        if entry(bits(x)) != (expected, 0):
            raise RuntimeError('exp2 oracle self-check failed: binary power/threshold')
    cases = ((HALF_MIN, 0), (HALF_MIN + Fraction(2) ** -2000, 1),
             (3 * HALF_MIN, 2), (5 * HALF_MIN, 2),
             (Fraction(1) + Fraction(2) ** -53, bits(1.0)),
             (Fraction(1) + Fraction(2) ** -53 + Fraction(2) ** -200,
              bits(1.0) + 1), (OVER, INF),
             (OVER - Fraction(2) ** 969, 0x7fefffffffffffff))
    for fr, expected in cases:
        if rounded(fr)[0] != expected:
            raise RuntimeError('exp2 oracle self-check failed: direct halfway rounding')
    signed_error_cases = (
        (Fraction(1) + Fraction(2) ** -54, bits(1.0), 0x3e800000),
        (Fraction(1) - Fraction(2) ** -55, bits(1.0), 0xbe800000),
        (3 * Fraction(2) ** -1076, 1, 0xbe800000),
        (5 * Fraction(2) ** -1076, 1, 0x3e800000),
        (Fraction(2) - Fraction(2) ** -54, bits(2.0), 0xbe800000),
    )
    for fr, expected, error in signed_error_cases:
        if rounded(fr) != (expected, error):
            raise RuntimeError('exp2 oracle self-check failed: signed true-ULP error')


def inputs(seed, count, fresh):
    rng = random.Random(seed)
    seen, words = set(), []

    def add(x):
        word = bits(x)
        if word not in seen:
            seen.add(word)
            words.append(word)

    def near(x):
        add(math.nextafter(x, -math.inf))
        add(x)
        add(math.nextafter(x, math.inf))

    for witness in ('0x1.1b65c88ac143ap+3', '-0x1.ff4e1f1239d69p+9'):
        add(float.fromhex(witness))
    for raw in (0, SIGN, INF, INF | SIGN, QNAN, QNAN | SIGN | 7,
                INF | 1, INF | SIGN | 1, 0x7fefffffffffffff,
                0xffefffffffffffff):
        add(value(raw))
    integers = set(range(-1075, 1025, 16 if fresh else 1))
    integers |= {-1075, -1074, -1023, -1022, -1, 0, 1, 1023, 1024}
    for k in sorted(integers):
        near(float(k))
    for k in (-1074, -1023, -1022, 0, 1, 1023):
        for j in range(0, 128, 8 if fresh else 1):
            near(k + j / 128.0)
            near(k + (j + 0.5) / 128.0)
    for x in (2.0 ** -54, -(2.0 ** -54), 2.0 ** -55, -(2.0 ** -55),
              -1075.0, -1074.0, -1022.0, 1024.0):
        near(x)
    mp.prec = 640
    midpoints = [0, 1, 2, 3, (1 << 52) - 1]
    midpoints += [rng.getrandbits(rng.randrange(1, 53))
                  for _ in range(32 if fresh else 256)]
    for m in midpoints:
        midpoint = (mp.mpf(m) + mp.mpf('0.5')) * mp.mpf(2) ** -1074
        near(float(mp.log(midpoint, 2)))
    for i in range(count):
        kind = i % 5
        if kind == 0:
            add(rng.uniform(-1100, 1100))
        elif kind == 1:
            add(rng.uniform(-10, 10))
        elif kind == 2:
            add(rng.uniform(-1075, -1022))
        elif kind == 3:
            add(rng.uniform(1020, 1024))
        else:
            add(value(rng.getrandbits(64)))
    return words


def main():
    self_check()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=20261026)
    parser.add_argument('--count', type=int, default=3000)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    if args.count < 0:
        parser.error('--count must be nonnegative')
    population = inputs(args.seed, args.count, args.fresh)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / 'exp2.corpus').open('w') as out:
        out.write('# Pinned oracle: tools/oracle/gen_corpus_exp2.py; MPFR %s gmpy2 %s mpmath %s\n' %
                  (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
        out.write('# seed %d count %d fresh %s entries %d\n' %
                  (args.seed, args.count, args.fresh, len(population)))
        out.write('# x_bits r_bits err_bits; err uses true binary64 ULP, subnormal grid included\n')
        for xb in population:
            rb, eb = entry(xb)
            out.write('%016x %016x %08x\n' % (xb, rb, eb))
    print('exp2: %d entries' % len(population), flush=True)


if __name__ == '__main__':
    main()
