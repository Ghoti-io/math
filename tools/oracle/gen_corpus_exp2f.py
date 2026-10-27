#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned binary32 exp2 references, directly rounded from exact rationals.

Rows: widened-binary64 input word, widened-binary64 result word, binary32
signed (exact-result)/true-binary32-ULP word. Directed MPFR600 bounds must
certify both stored roundings; independent mpmath640 must agree. Escalate
precision rather than guess at a boundary. Widening excludes raw sNaNs.

The extreme tails are certified analytically: x>=128 overflows binary32;
x<=-300 rounds to +0 and its error 2^(x+149)<=2^-151 rounds to +0 as well.
This avoids constructing powers with exponents as large as FLT_MAX. Exact
integer powers, including the -150 zero tie/error+.5, use rational arithmetic.
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

# Deterministic range/binade witnesses plus midpoint-inverse witnesses from
# seed20261027/count3000. b338aa3b and33b8aa3b have independently certified
# signed errors which round to -.5; adjacent witnesses cover the other side.
WITNESSES = (0x3f000000, 0xbf000000, 0xc3160000, 0xc315ffff,
             0xc2fc0001, 0x42ffffff, 0x33000000, 0xb3000000,
             0xb338aa3b, 0x33b8aa3b, 0xb338aa3c, 0x33b8aa3a,
             0xb338aa3d, 0xb338aa3a)


def finite_round(exact):
    result = round32(exact)
    if result == INF:
        return result, 0
    error = (exact - fraction(result)) / power(ulp_exp(exact))
    return result, round32(error)


def evaluate(raw, precision):
    x = value(raw)
    bounds = []
    for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
        with gmpy2.context(precision=precision, round=mode,
                          emin=gmpy2.get_emin_min(), emax=gmpy2.get_emax_max()):
            bounds.append(rational(gmpy2.exp2(gmpy2.mpfr(x))))
    low, high = bounds
    with mp.workprec(precision + 40):
        independent = mpmath_fraction(mp.power(2, mp.mpf(x)))
    if abs(independent - (low + high) / 2) > high * power(-precision + 8):
        raise RuntimeError('MPFR/mpmath value disagreement: exp2f(%08x)' % raw)
    if low <= 0 or ulp_exp(low) != ulp_exp(high):
        return None
    result = round32(low)
    if result != round32(high) or result != round32(independent):
        return None
    if result == INF:
        return result, 0
    unit = power(ulp_exp(low))
    errors = [(v - fraction(result)) / unit for v in (low, high, independent)]
    error_word = round32(errors[0])
    if any(round32(v) != error_word for v in errors[1:]):
        return None
    return result, error_word


def answer(raw):
    magnitude = raw & ~SIGN
    if magnitude > INF:
        return QNAN, 0
    if magnitude == INF:
        return (0 if raw & SIGN else INF), 0
    x = value(raw)
    if x >= 128:
        return INF, 0
    if x <= -300:
        return 0, 0
    if x == int(x):
        result = finite_round(power(int(x)))
        # MPFR and mpmath independently evaluate all manageable exact powers.
        with gmpy2.context(precision=600):
            direct = rational(gmpy2.exp2(gmpy2.mpfr(x)))
        with mp.workprec(640):
            independent = mpmath_fraction(mp.power(2, mp.mpf(x)))
        if direct != power(int(x)) or independent != direct:
            raise RuntimeError('independent exact-power disagreement: exp2f(%08x)' % raw)
        return result
    for precision in (600, 1200, 2400):
        result = evaluate(raw, precision)
        if result is not None:
            return result
    raise RuntimeError('uncertified binary32 rounding boundary: exp2f(%08x)' % raw)


def require(condition, description):
    if not condition:
        raise RuntimeError('exp2f oracle self-check failed: ' + description)


def write_corpus(destination, population, seed, count, fresh, reference=answer):
    """Publish only after every row certifies; a failed run preserves the old file."""
    maximum = (Fraction(0), 0)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent,
                                         prefix='.' + destination.name + '.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_exp2f.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function exp2f\n')
            out.write('# seed %d count %d fresh %s entries %d\n' %
                      (seed, count, fresh, len(population)))
            out.write('# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for raw in population:
                result, error = reference(raw)
                out.write('%016x %016x %08x\n' % (wide(raw), wide(result), error))
                if abs(fraction(error)) > maximum[0]:
                    maximum = (abs(fraction(error)), raw)
        # Same-directory rename is atomic, and the stream has flushed/closed.
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return maximum


def self_check():
    for raw, result in ((0, 0x3f800000), (SIGN, 0x3f800000),
                        (INF, INF), (INF | SIGN, 0),
                        (QNAN, QNAN), (QNAN | SIGN | 7, QNAN)):
        require(answer(raw) == (result, 0), 'special input')
    for exponent in range(-149, 128):
        require(answer(round32(Fraction(exponent))) == (round32(power(exponent)), 0),
                'exact integer power %d' % exponent)
    require(answer(round32(Fraction(-150))) == (0, 0x3f000000), '-150 target/error tie')
    require(answer(round32(Fraction(-299))) == (0, 0), '-299 error-word zero tie')
    require(answer(round32(Fraction(-300))) == (0, 0), 'analytical negative tail')
    require(answer(round32(Fraction(128))) == (INF, 0), 'analytical positive tail')
    for lower in (0, 1, 2, 0x007fffff, 0x00800000, 0x3f7fffff, 0x3f800000):
        midpoint = (fraction(lower) + fraction(lower + 1)) / 2
        require(round32(midpoint) == lower + (lower & 1), 'even/odd midpoint')
    for exact, result, error in ((power(-150), 0, 0x3f000000),
                                 (3 * power(-150), 2, 0xbf000000),
                                 (Fraction(1) - power(-26), 0x3f800000, 0xbe800000),
                                 (Fraction(1) + power(-25), 0x3f800000, 0x3e800000)):
        require(finite_round(exact) == (result, error), 'signed true-binade/subnormal error')
    require(round32(fraction(INF - 1) + power(103)) == INF, 'overflow tie')
    # Tiny noninteger inputs must retain the side of the binade and a signed
    # error. They cannot be classified as exact simply because result==1.
    require(answer(1)[0] == 0x3f800000 and answer(1)[1] != 0,
            'positive minimum input inexact error')
    require(answer(SIGN | 1)[0] == 0x3f800000 and answer(SIGN | 1)[1] & SIGN,
            'negative minimum input signed error')
    with tempfile.TemporaryDirectory(prefix='exp2f-atomic-selfcheck-') as directory:
        destination = Path(directory) / 'exp2f.corpus'
        original = b'previous certified corpus\n'
        destination.write_bytes(original)
        def planted_failure(raw):
            if raw == SIGN:
                raise ArithmeticError('planted second-row certification failure')
            return answer(raw)
        try:
            write_corpus(destination, [0, SIGN], 1, 0, False, planted_failure)
        except ArithmeticError:
            pass
        else:
            raise RuntimeError('exp2f oracle self-check accepted planted certification failure')
        require(destination.read_bytes() == original, 'failed run preserves committed corpus')
        require(list(Path(directory).iterdir()) == [destination], 'failed run removes temporary corpus')


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
            candidate = raw + delta
            if 0 <= candidate <= 0xffffffff and (candidate & ~SIGN) < INF:
                add(candidate)

    for raw in (0, SIGN, INF, INF | SIGN, QNAN, QNAN | SIGN | 7,
                QNAN | 0x003fffff, INF - 1, (INF - 1) | SIGN) + WITNESSES:
        add(raw)
    # Every normal input exponent and every subnormal bit length, both signs.
    for exponent in range(1, 255):
        for mantissa in (0, 1, 0x7fffff, rng.getrandbits(23)):
            raw = (exponent << 23) | mantissa
            add(raw)
            add(raw | SIGN)
    for length in range(1, 24):
        for raw in (1 << (length - 1), (1 << length) - 1,
                    rng.randrange(1 << (length - 1), 1 << length)):
            near(raw)
            near(raw | SIGN)
    for exponent in range(-150, 129):
        near(round32(Fraction(exponent)))
    for x in (-300, -299, -150, -149, -126, 0, 1, 127, 128):
        near(round32(Fraction(x)))
    for exponent in (-28, -27, -26, -25, -24):
        near(round32(power(exponent)))
        near(round32(-power(exponent)))
    # Every table cell seam and nearest-reduction half seam at representative
    # reconstruction exponents; no implementation coefficients are consulted.
    for base in (-150, -149, -127, -126, -1, 0, 1, 126, 127):
        for j in range(128):
            near(round32(Fraction(base) + Fraction(j, 128)))
            near(round32(Fraction(base) + Fraction(2 * j + 1, 256)))
    with gmpy2.context(precision=600):
        for i in range(64 if fresh else 384):
            raw = rng.randrange(0, INF - 1)
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            argument = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            near(round32(rational(gmpy2.log2(argument))))
        for raw in (0, 1, 2, 3, 0x007ffffe, 0x007fffff, 0x00800000,
                    0x3f7fffff, 0x3f800000, INF - 2):
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            argument = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            near(round32(rational(gmpy2.log2(argument))))
    for _ in range(count):
        add(rng.getrandbits(32))
        add(round32(Fraction.from_float(rng.uniform(-151, 129))))
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
    maximum = write_corpus(args.outdir / 'exp2f.corpus', population,
                           args.seed, args.count, args.fresh)
    print('exp2f: %d entries; largest reference-rounding error %.9g ULP at %08x' %
          (len(population), float(maximum[0]), maximum[1]), flush=True)


if __name__ == '__main__':
    main()
