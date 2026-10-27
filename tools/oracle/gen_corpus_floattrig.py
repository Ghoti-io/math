#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned binary32 trig oracle, independently evaluated by MPFR and mpmath.

Rows are exactly widened binary64 input/result words followed by a binary32
signed (exact-result)/ulp(exact) word. ULP is the true binary32 spacing at the
exact value, including binade boundaries and the subnormal floor. Neither
rounding step passes through binary64. Raw sNaNs are tested by the C++ unit
because widening them quiets them. Directed MPFR bounds must certify both
roundings; uncertainty escalates precision, then fails closed.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import random
import struct

import gmpy2
import mpmath
from mpmath import mp

SIGN = 0x80000000
INF = 0x7f800000
QNAN = 0x7fc00000
FUNCTIONS = ('sin', 'cos', 'tan')
# Seed 1793093951, count 100000 (311635 entries/function), 2026-10-27:
# largest observed errors were sin .50212651, cos .50004557, tan .50162548
# ULP. Preserve these independently certified witnesses for every seed.
SOAK_WITNESSES = (0xbf7be41c, 0xbf7fee51, 0xbf7707fe)


def value(raw):
    return struct.unpack('>f', struct.pack('>I', raw))[0]


def wide(raw):
    return struct.unpack('>Q', struct.pack('>d', value(raw)))[0]


def power(e):
    return Fraction(2) ** e


def fraction(raw):
    return Fraction.from_float(value(raw))


def floor_log2(x):
    x = abs(x)
    e = x.numerator.bit_length() - x.denominator.bit_length()
    return e - (x < power(e))


def ulp_exp(x):
    return max(floor_log2(x), -126) - 23


def round32(x, negative_zero=False):
    """Round an exact rational directly to binary32, ties to even."""
    sign = SIGN if x < 0 or (x == 0 and negative_zero) else 0
    x = abs(x)
    if x == 0:
        return sign
    exponent = max(floor_log2(x), -126)
    scaled = x / power(exponent - 23)
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r > scaled.denominator or (2 * r == scaled.denominator and q & 1):
        q += 1
    if q == 1 << 24:
        q >>= 1
        exponent += 1
    if exponent > 127:
        return sign | INF
    if q < 1 << 23:
        return sign | q
    return sign | ((exponent + 127) << 23) | (q - (1 << 23))


def rational(v):
    n, d = v.as_integer_ratio()
    return Fraction(int(n), int(d))


def mpmath_fraction(v):
    sign, man, exponent, _ = v._mpf_
    return (-1 if sign else 1) * Fraction(int(man)) * power(exponent)


def evaluate(fn, raw, precision):
    x = value(raw)
    bounds = []
    for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
        with gmpy2.context(precision=precision, round=mode,
                          emin=gmpy2.get_emin_min(), emax=gmpy2.get_emax_max()):
            bounds.append(rational(getattr(gmpy2, fn)(gmpy2.mpfr(x))))
    lo, hi = bounds
    # mpmath is an independent transcendental implementation, evaluated at
    # greater precision. Check its value as well as both stored rounding words.
    with mp.workprec(precision + 40):
        other = mpmath_fraction(getattr(mp, fn)(mp.mpf(x)))
    if abs(other - (lo + hi) / 2) > max(abs(lo), abs(hi)) * power(-precision + 8):
        raise RuntimeError('MPFR/mpmath value disagreement: %s(%08x)' % (fn, raw))
    if not lo or not hi or (lo < 0) != (hi < 0) or ulp_exp(lo) != ulp_exp(hi):
        return None
    rb = round32(lo)
    if rb != round32(hi) or rb != round32(other):
        return None
    if (rb & ~SIGN) == INF:
        return rb, 0
    unit = power(ulp_exp(lo))
    errors = [(v - fraction(rb)) / unit for v in (lo, hi, other)]
    eb = round32(errors[0])
    if any(round32(e) != eb for e in errors[1:]):
        return None
    return rb, eb


def answer(fn, raw):
    absolute = raw & ~SIGN
    if absolute >= INF:
        return QNAN, 0
    if absolute == 0:
        return (0x3f800000 if fn == 'cos' else raw), 0
    for precision in (600, 1200, 2400):
        result = evaluate(fn, raw, precision)
        if result is not None:
            return result
    raise RuntimeError('uncertified binary32 rounding boundary: %s(%08x)' % (fn, raw))


def self_check():
    # Exact ties with odd/even lower significands, both signs, subnormal ties,
    # the normal/subnormal boundary, overflow, and signed zero.
    for lower in (0, 1, 2, 0x007ffffe, 0x007fffff, 0x00800000,
                  0x3f7fffff, 0x3f800000, 0x3f800001):
        midpoint = (fraction(lower) + fraction(lower + 1)) / 2
        expected = lower + (lower & 1)
        assert round32(midpoint) == expected
        assert round32(-midpoint) == (expected | SIGN)
    assert round32(0, True) == SIGN
    assert round32(fraction(INF - 1) + power(103)) == INF
    assert round32(fraction(INF - 1) + power(102)) == INF - 1
    assert ulp_exp(Fraction(1) - power(-50)) == -24
    assert ulp_exp(Fraction(1) + power(-50)) == -23
    assert ulp_exp(power(-150)) == -149
    assert round32(Fraction(-1, 4)) == 0xbe800000
    assert round32(Fraction(1, 4)) == 0x3e800000
    for fn in FUNCTIONS:
        assert answer(fn, 0) == (0x3f800000 if fn == 'cos' else 0, 0)
        assert answer(fn, SIGN) == (0x3f800000 if fn == 'cos' else SIGN, 0)
        for raw in (INF, INF | SIGN, QNAN, QNAN | SIGN | 7):
            assert answer(fn, raw) == (QNAN, 0)
    assert answer('sin', 0x3f800000)[0] == 0x3f576aa4
    assert answer('cos', 0x3f800000)[0] == 0x3f0a5140
    assert answer('tan', 0x3f800000)[0] == 0x3fc75923
    assert answer('sin', 1) == (1, SIGN)  # negative error rounds to -0
    assert answer('tan', 1) == (1, 0)
    assert answer('cos', 1)[0] == 0x3f800000


def inputs(seed, count, fresh):
    rng = random.Random(seed)
    seen, rows = set(), []

    def add(raw):
        if not 0 <= raw <= 0xffffffff or raw in seen:
            return
        if (raw & ~SIGN) > INF and not raw & 0x00400000:
            return
        seen.add(raw)
        rows.append(raw)

    def near(raw):
        for delta in (-2, -1, 0, 1, 2):
            a = raw + delta
            if 0 <= a < INF:
                add(a)
                add(a | SIGN)

    for raw in (0, SIGN, INF, INF | SIGN, QNAN, QNAN | SIGN | 7,
                QNAN | 0x003fffff, INF - 1, (INF - 1) | SIGN):
        add(raw)
    for raw in SOAK_WITNESSES:
        add(raw)
        add(raw ^ SIGN)
    # Every normal exponent and every subnormal bit length, both signs.
    for exponent in range(1, 255):
        for mantissa in (0, 1, 0x7fffff, rng.getrandbits(23)):
            raw = (exponent << 23) | mantissa
            add(raw)
            add(raw | SIGN)
    for length in range(1, 24):
        for raw in (1 << (length - 1), (1 << length) - 1,
                    rng.randrange(1 << (length - 1), 1 << length)):
            near(raw)
    for x in (Fraction(1), Fraction(1, 2), Fraction(2), power(20), power(30),
              power(-126), power(-12), power(-27)):
        near(round32(x))
    with gmpy2.context(precision=600):
        pi = gmpy2.const_pi()
        # Near multiples and half multiples of pi/2, from small quadrants to
        # the largest finite float. The same pinned pi feeds all candidates.
        multipliers = list(range(1, 33 if fresh else 129))
        multipliers += [(1 << e) + rng.randrange(1 << min(e, 22))
                        for e in range(1, 128)]
        for k in multipliers:
            for offset in (gmpy2.mpfr(0), gmpy2.mpfr('0.5')):
                raw = round32(rational((gmpy2.mpfr(k) + offset) * pi / 2))
                if raw < INF:
                    near(raw)
        near(round32(rational(pi / 4)))
        near(round32(rational(pi / 2)))
        # Inverse images of output midpoints: round the input once to float,
        # then visit adjacent representable inputs. These seek difficult final
        # rounding independently of any implementation's polynomial choices.
        for sample in range(32 if fresh else 192):
            raw = rng.randrange(0x3e800000 if sample & 1 else 1, 0x3f800000)
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            m = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            for inverse in (gmpy2.asin, gmpy2.acos, gmpy2.atan):
                near(round32(rational(inverse(m))))
            raw = rng.randrange(1, INF - 1)
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            m = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            near(round32(rational(gmpy2.atan(m))))
    for _ in range(count):
        add(rng.getrandbits(32))
        # Ordinary magnitudes supplement exponent-uniform raw words.
        add(round32(Fraction.from_float(rng.uniform(-10000, 10000))))
        add(round32(Fraction.from_float(rng.uniform(-1, 1))))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', '--out', dest='outdir', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=20261027)
    parser.add_argument('--count', type=int, default=3000)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    if args.count < 0:
        parser.error('--count must be nonnegative')
    self_check()
    population = inputs(args.seed, args.count, args.fresh)
    args.outdir.mkdir(parents=True, exist_ok=True)
    for fn in FUNCTIONS:
        with (args.outdir / (fn + 'f.corpus')).open('w') as out:
            out.write('# Pinned oracle: tools/oracle/gen_corpus_floattrig.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# seed %d count %d fresh %s entries %d\n' %
                      (args.seed, args.count, args.fresh, len(population)))
            out.write('# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for raw in population:
                rb, eb = answer(fn, raw)
                out.write('%016x %016x %08x\n' % (wide(raw), wide(rb), eb))
        print('%sf: %d entries' % (fn, len(population)), flush=True)


if __name__ == '__main__':
    main()
