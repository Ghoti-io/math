#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned binary32 base-ten-log references, directly rounded from exact rationals.

Rows: widened-binary64 input word, widened-binary64 result word, binary32
signed (exact-result)/true-binary32-ULP word. Directed MPFR600 bounds must
certify both stored roundings; independent mpmath640 must agree. Escalate
precision rather than guess at a boundary. Widening excludes raw sNaNs.

All positive finite binary32 inputs widen to normal binary64 exactly. Only
input one has an exact zero result; decimal powers10^n,n=0..10 have exact
integer results. Other positive inputs have finite nonzero normal logarithms. Negative outputs and signed errors are
preserved without routing either target rounding through binary64.
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
# Exact representable decimal powers are derived from integer rationals,
# rather than recognizing rounded decimal literals as exact input values.
EXACT_POWERS = {}
for decimal_exponent in range(11):
    exact_input = Fraction(10) ** decimal_exponent
    raw_input = round32(exact_input)
    if fraction(raw_input) != exact_input:
        raise RuntimeError('exact decimal-power representability disagreement')
    EXACT_POWERS[raw_input] = decimal_exponent
# Fixed domain/one-region inputs and rounded10^11, whose returned integer11
# is inexact. The final four hard references were found by seed20261027,
# count3000, and preserve both output/error signs for later fresh runs.
WITNESSES = (1, 0x007fffff, 0x00800000, ONE - 2, ONE - 1, ONE,
             ONE + 1, ONE + 2, 0x3f7f0000, 0x3f810000,
             0x3f350000, 0x3fb50000, 0x51ba43b7,
             0x401e7ffe, 0x3ebf0001, 0x6a7338b3, 0x6bb42c44)


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
            bounds.append(rational(gmpy2.log10(gmpy2.mpfr(x))))
    low, high = bounds
    with mp.workprec(precision + 40):
        independent = mpmath_fraction(mp.log10(mp.mpf(x)))
    if abs(independent - (low + high) / 2) > max(abs(low), abs(high)) * power(-precision + 8):
        raise RuntimeError('MPFR/mpmath value disagreement: log10f(%08x)' % raw)
    if not low or not high or (low < 0) != (high < 0) or ulp_exp(low) != ulp_exp(high):
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
    if magnitude == 0:
        return INF | SIGN, 0
    if raw & SIGN:
        return QNAN, 0
    if magnitude == INF:
        return INF, 0
    if raw in EXACT_POWERS:
        exponent = EXACT_POWERS[raw]
        with gmpy2.context(precision=600):
            direct = rational(gmpy2.log10(gmpy2.mpfr(value(raw))))
        with mp.workprec(640):
            independent = mpmath_fraction(mp.log10(mp.mpf(value(raw))))
        if direct != exponent or round32(independent) != round32(Fraction(exponent)) or abs(independent - exponent) > power(-590):
            raise RuntimeError('independent exact-decimal-power disagreement')
        return round32(Fraction(exponent)), 0
    for precision in (600, 1200, 2400):
        result = evaluate(raw, precision)
        if result is not None:
            return result
    raise RuntimeError('uncertified binary32 rounding boundary: log10f(%08x)' % raw)


def require(condition, description):
    if not condition:
        raise RuntimeError('log10f oracle self-check failed: ' + description)


def write_corpus(destination, population, seed, count, fresh, reference=answer):
    """Publish only after every row certifies; a failed run preserves the old file."""
    maximum = (Fraction(0), 0)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent,
                                         prefix='.' + destination.name + '.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_log10f.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function log10f\n')
            out.write('# seed %d count %d fresh %s entries %d\n' %
                      (seed, count, fresh, len(population)))
            out.write('# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for raw in population:
                result, error = reference(raw)
                out.write('%016x %016x %08x\n' % (wide(raw), wide(result), error))
                if abs(fraction(error)) > maximum[0]:
                    maximum = (abs(fraction(error)), raw)
        # Same-directory rename is atomic, and the stream has flushed/closed.
        temporary.chmod(destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return maximum


def self_check():
    # Fixed inverse-log candidates use arguments in[-40,38]. Certify that
    # this entire interval maps inside finite nonzero binary32 input range.
    with gmpy2.context(precision=600, round=gmpy2.RoundDown):
        lower_inverse = rational(gmpy2.mpfr(10) ** -40)
    with gmpy2.context(precision=600, round=gmpy2.RoundUp):
        upper_inverse = rational(gmpy2.mpfr(10) ** 38)
    require(lower_inverse > fraction(1) and upper_inverse < fraction(INF - 1),
            'fixed inverse candidates inside finite positive input range')
    for raw, result in ((0, INF | SIGN), (SIGN, INF | SIGN),
                        (INF, INF), (INF | SIGN, QNAN),
                        (QNAN, QNAN), (QNAN | SIGN | 7, QNAN),
                        (0xbf800000, QNAN), (ONE, 0)):
        require(answer(raw) == (result, 0), 'special input')
    for raw in (1, 0x007fffff, 0x00800000, 0x3e800000, 0x3f000000,
                ONE - 1, ONE + 1, 0x40000000, 0x40800000, INF - 1):
        result, error = answer(raw)
        require(0x00800000 <= (result & ~SIGN) < INF, 'positive non-one result normal')
        require(bool(result & SIGN) == (raw < ONE), 'logarithm output sign')
        require((error & ~SIGN) != 0, 'non-one reference inexact error')
    require(answer(0x40000000) == (0x3e9a209b, 0xbef60860), 'log10(2) rounded result and signed error')
    require(answer(0x3f000000) == (0xbe9a209b, 0x3ef60860), 'log10(1/2) rounded result and signed error')
    for raw, exponent in EXACT_POWERS.items():
        require(answer(raw) == (round32(Fraction(exponent)), 0), 'exact decimal power result/error')
        require((Fraction(5) ** exponent).numerator.bit_length() <= 24,
                'exact decimal-power odd significand fits24 bits')
    require((5 ** 11).bit_length() > 24, 'next decimal power not exactly representable')
    require(answer(0x51ba43b7) == (0x41300000, 0xbc18cdc5),
            'rounded10^11 remains inexact despite integer result')
    for lower in (0, 1, 2, 0x007fffff, 0x00800000, 0x3f7fffff, 0x3f800000):
        midpoint = (fraction(lower) + fraction(lower + 1)) / 2
        require(round32(midpoint) == lower + (lower & 1), 'even/odd midpoint')
    for exact, result, error in ((power(-150), 0, 0x3f000000),
                                 (3 * power(-150), 2, 0xbf000000),
                                 (Fraction(1) - power(-26), 0x3f800000, 0xbe800000),
                                 (Fraction(1) + power(-25), 0x3f800000, 0x3e800000)):
        require(finite_round(exact) == (result, error), 'signed true-binade/subnormal error')
    require(round32(fraction(INF - 1) + power(103)) == INF, 'overflow tie')
    # Explicit signed-error checks on both sides of a negative binade boundary.
    require(finite_round(-Fraction(1) + power(-26)) == (0xbf800000, 0x3e800000),
            'negative result exact value toward zero')
    require(finite_round(-Fraction(1) - power(-25)) == (0xbf800000, 0xbe800000),
            'negative result exact value away from zero')
    # Exercise failures before any data row, partway through, and at the
    # last row. Each case must leave the public destination and directory
    # exactly as they were before certification began.
    cases = (([0], 0, False), ([0, SIGN], SIGN, True),
             ([0, SIGN, 0x40000000], 0x40000000, True))
    for population, fail_at, existing in cases:
        with tempfile.TemporaryDirectory(prefix='log10f-atomic-selfcheck-') as directory:
            destination = Path(directory) / 'log10f.corpus'
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
                raise RuntimeError('log10f oracle self-check accepted planted certification failure')
            if existing:
                require(destination.read_bytes() == original,
                        'failed run preserves committed corpus')
            else:
                require(not destination.exists(), 'failed first row leaves destination absent')
            expected_files = [destination] if existing else []
            require(list(Path(directory).iterdir()) == expected_files,
                    'failed run removes temporary corpus')


    for mode in (None, 0o640, 0o644):
        with tempfile.TemporaryDirectory(prefix='log10f-mode-selfcheck-') as directory:
            destination = Path(directory) / 'log10f.corpus'
            if mode is not None:
                destination.write_bytes(b'previous corpus\n')
                destination.chmod(mode)
            write_corpus(destination, [ONE], 1, 0, False)
            require(destination.stat().st_mode & 0o777 == (0o644 if mode is None else mode),
                    'atomic publication preserves readable permissions')


def inputs(seed, count, fresh, diagnostics=None):
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
    for exponent in range(-45, 39):
        raw = round32(Fraction(10) ** exponent)
        near(raw)
        near(raw | SIGN)
    for integer in range(-16, 130):
        near(round32(Fraction(integer)))
    for raw in (ONE, 0x007fffff, 0x00800000, 0x3f7f0000, 0x3f810000):
        near(raw)
    # Independent bit geometry of normalized [181/256,181/128): all128
    # table-row seams and half seams, repeated across representative scales.
    # These describe inputs only; reference values never use table constants.
    import struct
    for exponent in (-126, -1, 0, 1, 127):
        for j in range(129):
            dbits = 0x3fe6a00000000000 + (j << 45)
            m = struct.unpack('>d', struct.pack('>Q', dbits))[0]
            near(round32(Fraction.from_float(m) * power(exponent)))
            if j < 128:
                dbits += 1 << 44
                m = struct.unpack('>d', struct.pack('>Q', dbits))[0]
                near(round32(Fraction.from_float(m) * power(exponent)))
    # Invert output midpoints with10^argument, admitting only certified finite-input
    # inverses. Candidate output magnitudes are bounded by46, so no huge power
    # can occur even before the min/max-input interval test.
    with gmpy2.context(precision=600):
        minimum = gmpy2.mpfr(value(1))
        maximum = gmpy2.mpfr(value(INF - 1))
        midpoint_words = []
        if fresh:
            # Cover30 useful output binades with both signs. Two separated
            # mantissa strata avoid clustering at the one-input rounding cell.
            # The top binade is capped at+38/-44, inside the finite input
            # inverse range, and all candidates retain directed range checks.
            for exponent in range(-24, 6):
                field = (exponent + 127) << 23
                for sign in (0, SIGN):
                    limit = (round32(Fraction(44 if sign else 38)) - field
                             if exponent == 5 else 1 << 23)
                    for low, high in ((limit // 8, 3 * limit // 8),
                                      (5 * limit // 8, 7 * limit // 8)):
                        midpoint_words.append(field | rng.randrange(low, high) | sign)
        else:
            # Keep the committed stream and its random-call order fixed.
            for i in range(512):
                magnitude = rng.randrange(1, round32(Fraction(46)))
                midpoint_words.append(magnitude | (SIGN if rng.getrandbits(1) else 0))
        distinct_midpoints, covered_binades = set(), set()
        for raw in midpoint_words:
            neighbor = raw - 1 if raw & SIGN else raw + 1
            midpoint = (fraction(raw) + fraction(neighbor)) / 2
            argument = gmpy2.mpfr(midpoint.numerator) / midpoint.denominator
            low, high = [], []
            for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
                with gmpy2.context(precision=600, round=mode):
                    (low if mode == gmpy2.RoundDown else high).append(gmpy2.mpfr(10) ** argument)
            if low[0] >= minimum and high[0] <= maximum:
                candidate = round32(rational((low[0] + high[0]) / 2))
                if 1 <= candidate < INF:
                    near(candidate)
                    distinct_midpoints.add(candidate)
                    covered_binades.add(((raw & ~SIGN) >> 23) - 127)
        if fresh:
            below = sum(raw < ONE for raw in distinct_midpoints)
            above = sum(raw > ONE for raw in distinct_midpoints)
            require(covered_binades == set(range(-24, 6)), 'fresh midpoint binade coverage')
            require(len(distinct_midpoints) >= 90 and below >= 40 and above >= 40,
                    'fresh distinct finite midpoint coverage')
            if diagnostics is not None:
                diagnostics.update(midpoints=len(distinct_midpoints), below=below,
                                   above=above, binades=len(covered_binades))
        for x in (Fraction(-40), Fraction(-1), Fraction(1), Fraction(38),
                  -power(-24), power(-23), Fraction(-1, 2), Fraction(1, 2)):
            argument = gmpy2.mpfr(x.numerator) / x.denominator
            inverse = gmpy2.mpfr(10) ** argument
            if minimum <= inverse <= maximum:
                near(round32(rational(inverse)))
    for _ in range(count):
        add(rng.getrandbits(32))
        add(round32(Fraction.from_float(rng.uniform(-2, 2))))
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
    diagnostics = {}
    population = inputs(args.seed, args.count, args.fresh, diagnostics)
    if args.fresh:
        print('log10f fresh inverse midpoints: %(midpoints)d distinct finite, %(below)d below1, %(above)d above1, %(binades)d binades' % diagnostics, flush=True)
    args.outdir.mkdir(parents=True, exist_ok=True)
    maximum = write_corpus(args.outdir / 'log10f.corpus', population,
                           args.seed, args.count, args.fresh)
    print('log10f: %d entries; largest reference-rounding error %.9g ULP at %08x' %
          (len(population), float(maximum[0]), maximum[1]), flush=True)


if __name__ == '__main__':
    main()
