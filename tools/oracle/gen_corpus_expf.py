#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned binary32 natural-exp references, directly rounded from exact rationals.

Rows: widened-binary64 input word, widened-binary64 result word, binary32
signed (exact-result)/true-binary32-ULP word. Directed MPFR600 bounds must
certify both stored roundings; independent mpmath640 must agree. Escalate
precision rather than guess at a boundary. Widening excludes raw sNaNs.

The coarse tails are certified analytically: x>=89 overflows binary32;
x<=-256 rounds to +0 and its positive error also rounds to +0. The precise
float-input boundaries are maintained directed-log certificates. Only zero
has an exact finite result; every other manageable input is evaluated by both
independent transcendental implementations.
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

OVER_FIRST = 0x42b17218
ZERO_LAST = 0xc2cff1b5
SUBNORMAL_LAST = 0xc2aeac50
# Certified boundary/tiny inputs and midpoint witnesses from seed20261027,
# count3000: b3000000 has a signed true-ULP error rounding to -.5; 33800000
# and adjacent input words cover final rounding on the opposite side of one.
WITNESSES = (OVER_FIRST, OVER_FIRST - 1, ZERO_LAST, ZERO_LAST - 1,
             SUBNORMAL_LAST, SUBNORMAL_LAST - 1,
             0x32800000, 0xb2800000, 0x3f800000, 0xbf800000,
             0xb3000000, 0xb3000001, 0xb2ffffff, 0x33800000,
             0x337fffff, 0x33800001)


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
            bounds.append(rational(gmpy2.exp(gmpy2.mpfr(x))))
    low, high = bounds
    with mp.workprec(precision + 40):
        independent = mpmath_fraction(mp.exp(mp.mpf(x)))
    if abs(independent - (low + high) / 2) > high * power(-precision + 8):
        raise RuntimeError('MPFR/mpmath value disagreement: expf(%08x)' % raw)
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
    if x == 0:
        return 0x3f800000, 0
    if x >= 89:
        return INF, 0
    if x <= -256:
        return 0, 0
    for precision in (600, 1200, 2400):
        result = evaluate(raw, precision)
        if result is not None:
            return result
    raise RuntimeError('uncertified binary32 rounding boundary: expf(%08x)' % raw)


def require(condition, description):
    if not condition:
        raise RuntimeError('expf oracle self-check failed: ' + description)


def write_corpus(destination, population, seed, count, fresh, reference=answer):
    """Publish only after every row certifies; a failed run preserves the old file."""
    maximum = (Fraction(0), 0)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent,
                                         prefix='.' + destination.name + '.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_expf.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function expf\n')
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


def bracket_proved(low, high, below, above):
    return fraction(below) < low <= high < fraction(above)


def certify_thresholds():
    cases = (('overflow', power(128) - power(103), OVER_FIRST - 1, OVER_FIRST),
             ('zero', power(-150), ZERO_LAST, ZERO_LAST - 1),
             ('normal', power(-126), SUBNORMAL_LAST, SUBNORMAL_LAST - 1),
             ('rounded normal', power(-126) - power(-150), SUBNORMAL_LAST, SUBNORMAL_LAST - 1))
    for name, target, below, above in cases:
        bounds = []
        for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
            with gmpy2.context(precision=600, round=mode):
                argument = gmpy2.mpfr(target.numerator) / target.denominator
                require(rational(argument) == target, 'exact threshold log argument')
                bounds.append(rational(gmpy2.log(argument)))
        low, high = bounds
        require(bracket_proved(low, high, below, above), name + ' float threshold bracket')
        with mp.workprec(640):
            independent = mpmath_fraction(mp.log(mp.mpf(target.numerator) / target.denominator))
        require(low <= independent <= high, name + ' independent log certificate')
        for raw in (below, above):
            endpoints = []
            for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
                with gmpy2.context(precision=600, round=mode):
                    endpoints.append(rational(gmpy2.exp(gmpy2.mpfr(value(raw)))))
            require(endpoints[1] < target if raw == below else endpoints[0] > target,
                    name + ' directed endpoint exp certificate')
            with mp.workprec(640):
                independent = mpmath_fraction(mp.exp(mp.mpf(value(raw))))
            require(endpoints[0] <= independent <= endpoints[1],
                    name + ' independent endpoint exp certificate')
    ln2_bounds = []
    for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
        with gmpy2.context(precision=600, round=mode):
            ln2_bounds.append(rational(gmpy2.log(gmpy2.mpfr(2))))
    low, high = ln2_bounds
    require(bracket_proved(-150 * high, -150 * low, ZERO_LAST, ZERO_LAST - 1),
            'negative-log endpoint reversal')
    require(bracket_proved(-126 * high, -126 * low, SUBNORMAL_LAST, SUBNORMAL_LAST - 1),
            'negative minnormal endpoint reversal')
    require(299 * high < 256, 'coarse negative tail error <half minimum error word')
    require(fraction(OVER_FIRST) < 89, 'coarse positive overflow tail')
    # Do not accept an interval touching a floating endpoint or crossing it.
    require(not bracket_proved(fraction(OVER_FIRST - 1), fraction(OVER_FIRST - 1),
                               OVER_FIRST - 1, OVER_FIRST), 'adversarial lower endpoint rejected')
    require(not bracket_proved(fraction(OVER_FIRST - 1) + power(-40), fraction(OVER_FIRST),
                               OVER_FIRST - 1, OVER_FIRST), 'adversarial upper endpoint rejected')


def self_check():
    certify_thresholds()
    for raw, result in ((0, 0x3f800000), (SIGN, 0x3f800000),
                        (INF, INF), (INF | SIGN, 0),
                        (QNAN, QNAN), (QNAN | SIGN | 7, QNAN)):
        require(answer(raw) == (result, 0), 'special input')
    require(answer(OVER_FIRST) == (INF, 0), 'first overflow input')
    require(answer(OVER_FIRST - 1)[0] < INF, 'last finite input')
    require(answer(ZERO_LAST)[0] == 0 and answer(ZERO_LAST)[1] != 0, 'last zero input/error')
    require(answer(ZERO_LAST - 1)[0] == 1, 'first nonzero input')
    require(0 < answer(SUBNORMAL_LAST)[0] < 0x00800000, 'last subnormal input')
    require(answer(SUBNORMAL_LAST - 1)[0] >= 0x00800000, 'first normal input')
    require(answer(round32(Fraction(-256))) == (0, 0), 'analytical negative tail')
    require(answer(round32(Fraction(89))) == (INF, 0), 'analytical positive tail')
    require(answer(0x3f800000)[0] == 0x402df854, 'exp(1) rounded result')
    require(answer(0xbf800000)[0] == 0x3ebc5ab2, 'exp(-1) rounded result')
    for integer in (-103, -100, -88, -2, 2, 64, 88):
        result, error = answer(round32(Fraction(integer)))
        require(result != round32(power(integer)),
                'natural exponential differs from binary power at %d' % integer)
        require((error & ~SIGN) != 0, 'nonzero integer has inexact reference error')
        if integer < value(SUBNORMAL_LAST):
            require(0 < result < 0x00800000, 'integer exponential subnormal class')
        else:
            require(0x00800000 <= result < INF, 'integer exponential normal class')
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
    # Exercise failures before any data row, partway through, and at the
    # last row. Each case must leave the public destination and directory
    # exactly as they were before certification began.
    cases = (([0], 0, False), ([0, SIGN], SIGN, True),
             ([0, SIGN, 0x3f800000], 0x3f800000, True))
    for population, fail_at, existing in cases:
        with tempfile.TemporaryDirectory(prefix='expf-atomic-selfcheck-') as directory:
            destination = Path(directory) / 'expf.corpus'
            original = b'previous certified corpus\n'
            if existing:
                destination.write_bytes(original)
            def planted_failure(raw):
                if raw == fail_at:
                    raise ArithmeticError('planted row certification failure')
                return answer(raw)
            try:
                write_corpus(destination, population, 1, 0, False, planted_failure)
            except ArithmeticError:
                pass
            else:
                raise RuntimeError('expf oracle self-check accepted planted certification failure')
            if existing:
                require(destination.read_bytes() == original,
                        'failed run preserves committed corpus')
            else:
                require(not destination.exists(), 'failed first row leaves destination absent')
            expected_files = [destination] if existing else []
            require(list(Path(directory).iterdir()) == expected_files,
                    'failed run removes temporary corpus')


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
    for integer in range(-105, 90):
        near(round32(Fraction(integer)))
    for raw in (OVER_FIRST, ZERO_LAST, SUBNORMAL_LAST):
        near(raw)
    for x in (-256, 89, -1, 0, 1):
        near(round32(Fraction(x)))
    for exponent in (-28, -27, -26, -25, -24):
        near(round32(power(exponent)))
        near(round32(-power(exponent)))
    with gmpy2.context(precision=600):
        ln2 = gmpy2.log(gmpy2.mpfr(2))
        for exponent in range(-150, 129):
            near(round32(rational(exponent * ln2)))
        # All 128 table seams and half seams at representative output exponents.
        for base in (-150, -149, -127, -126, -1, 0, 1, 126, 127):
            for j in range(128):
                for offset in (Fraction(j, 128), Fraction(2 * j + 1, 256)):
                    argument = Fraction(base) + offset
                    argument = gmpy2.mpfr(argument.numerator) / argument.denominator
                    near(round32(rational(argument * ln2)))
        for i in range(64 if fresh else 384):
            raw = rng.randrange(0, INF - 1)
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            argument = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            near(round32(rational(gmpy2.log(argument))))
        for raw in (0, 1, 2, 3, 0x007ffffe, 0x007fffff, 0x00800000,
                    0x3f7fffff, 0x3f800000, INF - 2):
            midpoint = (fraction(raw) + fraction(raw + 1)) / 2
            argument = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            near(round32(rational(gmpy2.log(argument))))
    for _ in range(count):
        add(rng.getrandbits(32))
        add(round32(Fraction.from_float(rng.uniform(-105, 90))))
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
    maximum = write_corpus(args.outdir / 'expf.corpus', population,
                           args.seed, args.count, args.fresh)
    print('expf: %d entries; largest reference-rounding error %.9g ULP at %08x' %
          (len(population), float(maximum[0]), maximum[1]), flush=True)


if __name__ == '__main__':
    main()
