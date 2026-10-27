#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned MPFR600/mpmath640 real-cube-root oracle: x_bits r_bits signed_err_bits.

Both references are rationalized and rounded independently to binary64. The
signed error uses spacing at the true root; finite nonzero roots are normal.
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
    if not fr:
        return 0, 0
    unit = Fraction(2) ** (exponent(abs(fr)) - 52)
    scaled = abs(fr) / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r > scaled.denominator or (2 * r == scaled.denominator and q & 1):
        q += 1
    rf = q * unit * (-1 if fr < 0 else 1)
    result = float(rf)
    if Fraction.from_float(result) != rf:
        raise RuntimeError('cbrt oracle target rounding was not exact')
    error = (fr - rf) / unit
    ebits = struct.unpack('>I', struct.pack('>f', float(error)))[0]
    return bits(result), ebits


def mp_fraction(x):
    mantissa, power = mp.frexp(x)
    significant = int(mp.ldexp(mantissa, mp.prec))
    return Fraction(significant) * Fraction(2) ** (int(power) - mp.prec)


def normalized_error(word):
    return 0 if (word & 0x7fffffff) == 0 else word


def error_value(word):
    return struct.unpack('>f', struct.pack('>I', word))[0]


def error_neighbor(word, upward):
    word = normalized_error(word)
    if word == 0:
        return 1 if upward else 0x80000001
    if bool(word & 0x80000000) == upward:
        return word - 1
    return word + 1


def certify(xb, rb, eb):
    """Certify BOTH rounded words by exact rational cube comparisons.

    The cube is globally monotone. Root rounding intervals and error rounding
    intervals can therefore be tested against the exact binary64 input without
    relying on any fixed-precision approximation to the real cube root.
    """
    x = Fraction.from_float(value(xb))
    root = value(rb)
    if not math.isfinite(root) or root == 0:
        raise RuntimeError('cbrt oracle certificate failed: non-normal finite root')
    rf = Fraction.from_float(root)
    low = (Fraction.from_float(math.nextafter(root, -math.inf)) + rf) / 2
    high = (Fraction.from_float(math.nextafter(root, math.inf)) + rf) / 2
    lo_cube, hi_cube = low ** 3, high ** 3
    if x < lo_cube or x > hi_cube or ((x == lo_cube or x == hi_cube) and rb & 1):
        raise RuntimeError('cbrt oracle certificate failed: nearest binary64 root')
    eb = normalized_error(eb)
    if rf ** 3 == x:
        if eb != 0:
            raise RuntimeError('cbrt oracle certificate failed: nonzero error for exact cube')
        return eb
    if (eb & 0x7fffffff) > 0x3f000000:
        raise RuntimeError('cbrt oracle certificate failed: invalid signed-error range')
    # floor(log2(abs(cbrt(x)))) = floor(floor(log2(abs(x)))/3).
    # This derives the true root's ULP independently of MPFR and mpmath.
    unit = Fraction(2) ** (exponent(abs(x)) // 3 - 52)
    ef = Fraction.from_float(error_value(eb))
    before = Fraction.from_float(error_value(error_neighbor(eb, False)))
    after = Fraction.from_float(error_value(error_neighbor(eb, True)))
    low = rf + ((before + ef) / 2) * unit
    high = rf + ((ef + after) / 2) * unit
    lo_cube, hi_cube = low ** 3, high ** 3
    if x < lo_cube or x > hi_cube or ((x == lo_cube or x == hi_cube) and eb & 1):
        raise RuntimeError('cbrt oracle certificate failed: nearest binary32 signed error')
    return eb


def entry(xb):
    x = value(xb)
    a = xb & ~SIGN
    if a > INF:
        return QNAN, 0
    if a == 0 or a == INF:
        return xb, 0
    with gmpy2.context(precision=600, emin=gmpy2.get_emin_min(),
                      emax=gmpy2.get_emax_max(), round=gmpy2.RoundToNearest):
        reference = gmpy2.cbrt(gmpy2.mpfr(x))
    n, d = reference.as_integer_ratio()
    fr = Fraction(int(n), int(d))
    mp.prec = 640
    independent = mp.root(mp.mpf(abs(x)), 3)
    if x < 0:
        independent = -independent
    other = mp_fraction(independent)
    if abs(fr - other) > abs(fr) * Fraction(2) ** -400:
        raise RuntimeError('MPFR and mpmath disagree for cbrt(%016x)' % xb)
    result = rounded(fr)
    independent_result = rounded(other)
    if result[0] != independent_result[0]:
        raise RuntimeError('MPFR and mpmath rounded cbrt results disagree for %016x' % xb)
    eb = normalized_error(result[1])
    if eb != normalized_error(independent_result[1]):
        raise RuntimeError('MPFR and mpmath signed-error words disagree for %016x' % xb)
    return result[0], certify(xb, result[0], eb)


def self_check():
    cases = ((0, 0), (SIGN, SIGN), (INF, INF), (INF | SIGN, INF | SIGN),
             (QNAN | 7, QNAN), (INF | 1, QNAN),
             (bits(1.0), bits(1.0)), (bits(8.0), bits(2.0)),
             (bits(27.0), bits(3.0)), (bits(-27.0), bits(-3.0)),
             (bits(0.125), bits(0.5)), (1, (1023 - 358) << 52),
             (0x7fe0000000000000, (1023 + 341) << 52))
    for xb, expected in cases:
        if entry(xb) != (expected, 0):
            raise RuntimeError('cbrt oracle self-check failed: exact cube/special')
    signed_cases = (
        (Fraction(1) + Fraction(2) ** -54, bits(1.0), 0x3e800000),
        (-Fraction(1) - Fraction(2) ** -54, bits(-1.0), 0xbe800000),
        (Fraction(1) - Fraction(2) ** -55, bits(1.0), 0xbe800000),
        (-Fraction(1) + Fraction(2) ** -55, bits(-1.0), 0x3e800000),
        (Fraction(2) - Fraction(2) ** -54, bits(2.0), 0xbe800000),
    )
    for fr, expected, error in signed_cases:
        if rounded(fr) != (expected, error):
            raise RuntimeError('cbrt oracle self-check failed: signed true-ULP error')
    # The certificates must reject an incorrect selected root and an incorrect
    # signed-error word, not merely reproduce the high-precision calculation.
    certified = entry(bits(2.0))
    for wrong_root, wrong_error in ((certified[0] + 1, certified[1]),
                                    (certified[0], certified[1] ^ 0x80000000)):
        try:
            certify(bits(2.0), wrong_root, wrong_error)
        except RuntimeError as error:
            if not str(error).startswith('cbrt oracle certificate failed:'):
                raise
        else:
            raise RuntimeError('cbrt oracle self-check failed: certificate accepted wrong word')
    midpoint = Fraction(1) + Fraction(2) ** -53
    odd_midpoint = Fraction(1) + 3 * Fraction(2) ** -53
    if (rounded(midpoint)[0] != bits(1.0) or
            rounded(midpoint + Fraction(2) ** -200)[0] != bits(1.0) + 1 or
            rounded(odd_midpoint)[0] != bits(1.0) + 2 or
            rounded(-odd_midpoint)[0] != bits(-1.0) + 2):
        raise RuntimeError('cbrt oracle self-check failed: nearest-even midpoint')


def inputs(seed, count, fresh):
    rng = random.Random(seed)
    seen, words = set(), []

    def add_raw(raw):
        if 0 <= raw < (1 << 64) and raw not in seen:
            seen.add(raw)
            words.append(raw)

    def add(x):
        add_raw(bits(x))

    def signed_near(x):
        for y in (math.nextafter(x, -math.inf), x, math.nextafter(x, math.inf)):
            add(y)
            add(-y)

    # Measured witnesses retained independently of random population order:
    # seed20261026/count3000 and seed1793071801/count100000 respectively.
    for witness in ('0x1.d861b2bcb5897p+511', '0x1.1dab007db6d06p-846'):
        x = float.fromhex(witness)
        add(x)
        add(-x)
    for raw in (0, SIGN, INF, INF | SIGN, QNAN, QNAN | SIGN | 7,
                INF | 1, INF | SIGN | 1, 0x7fefffffffffffff,
                0xffefffffffffffff):
        add_raw(raw)
    powers = set(range(-1074, 1024, 16 if fresh else 1))
    powers |= {-1074, -1073, -1023, -1022, -1021, -1020, -3, -2, -1, 0, 1, 2, 1021, 1022, 1023}
    for e in sorted(powers):
        signed_near(math.ldexp(1.0, e))
    # Every seed-row boundary in all three exponent residue classes, followed
    # by a few boundary rows scaled to extreme positive/negative exponents.
    for e in (0, 1, 2):
        for j in range(0, 65, 8 if fresh else 1):
            signed_near(math.ldexp(1 + j / 64.0, e))
        for j in range(0, 64, 8 if fresh else 1):
            y = math.ldexp(1 + (2 * j + 1) / 128.0, e)
            add(y)
            add(-y)
    for e in (-1022, -1021, -1020, 1020, 1021, 1022, 1023):
        for j in (0, 1, 31, 32, 63, 64):
            try:
                signed_near(math.ldexp(1 + j / 64.0, e))
            except OverflowError:
                pass
    # Inputs that are exact integer cubes, their neighbors, and scaled cubes.
    for n in range(1, 9 if fresh else 65):
        signed_near(float(n ** 3))
    for n in (3, 5, 7, 9, 11, 13):
        for q in (-350, -340, -1, 1, 300, 330):
            signed_near(math.ldexp(float(n ** 3), 3 * q))
    # Each subnormal bit length and the large/small mantissas of that length.
    for k in range(52):
        for raw in (1 << k, (1 << (k + 1)) - 1):
            add_raw(raw)
            add_raw(raw | SIGN)
    for _ in range(32 if fresh else 256):
        raw = rng.randrange(1, 1 << 52)
        add_raw(raw)
        add_raw(raw | SIGN)
    # Cube the exact midpoint of two neighboring candidate roots. Rounding
    # this rational input to binary64 locates hard output-rounding cases.
    for _ in range(16 if fresh else 128):
        y = math.ldexp(1 + rng.getrandbits(52) * 2.0 ** -52, rng.randrange(-350, 341))
        midpoint = (Fraction.from_float(y) + Fraction.from_float(math.nextafter(y, math.inf))) / 2
        try:
            signed_near(float(midpoint ** 3))
        except OverflowError:
            pass
    for i in range(count):
        if i % 3 == 0:
            add_raw(rng.getrandbits(64))
        elif i % 3 == 1:
            add(rng.uniform(-8, 8))
        else:
            raw = rng.randrange(1, INF)
            add_raw(raw | (SIGN if rng.getrandbits(1) else 0))
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
    with (args.out / 'cbrt.corpus').open('w') as out:
        out.write('# Pinned oracle: tools/oracle/gen_corpus_cbrt.py; MPFR %s gmpy2 %s mpmath %s\n' %
                  (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
        out.write('# seed %d count %d fresh %s entries %d\n' %
                  (args.seed, args.count, args.fresh, len(population)))
        out.write('# x_bits r_bits err_bits; err uses true binary64 ULP of the signed real root\n')
        for xb in population:
            rb, eb = entry(xb)
            out.write('%016x %016x %08x\n' % (xb, rb, eb))
    print('cbrt: %d entries' % len(population), flush=True)


if __name__ == '__main__':
    main()
