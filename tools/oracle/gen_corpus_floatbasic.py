#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned exact binary32 basic-operation corpora; every word is widened binary64.

Unary rows: x_bits r_bits. copysignf rows: x_bits y_bits r_bits. Signaling NaNs
are excluded because widening quiets them; raw unit tests cover their flags.
Rounding uses exact Fraction integers cross-checked against MPFR. sqrt uses
MPFR24 round-to-nearest certified by exact midpoint-square inequalities.
"""
import argparse
from fractions import Fraction
import math
from pathlib import Path
import random
import struct

import gmpy2

SIGN = 0x80000000
INF = 0x7f800000
QUIET = 0x00400000
QNAN = 0x7fc00000
UNARY = ('floorf', 'ceilf', 'truncf', 'roundf', 'rintf', 'fabsf', 'sqrtf')


def value(word):
    return struct.unpack('>f', struct.pack('>I', word))[0]


def word(x):
    return struct.unpack('>I', struct.pack('>f', x))[0]


def wide(word32):
    return struct.unpack('>Q', struct.pack('>d', value(word32)))[0]


def signaling(raw):
    return (raw & ~SIGN) > INF and not (raw & QUIET)


def integer_answer(fn, raw):
    a = raw & ~SIGN
    if a > INF:
        return QNAN
    if a == INF or a == 0:
        return raw
    fr = Fraction.from_float(value(raw))
    n, d = fr.numerator, fr.denominator
    if fn == 'floorf':
        result = n // d
    elif fn == 'ceilf':
        result = -((-n) // d)
    elif fn == 'truncf':
        result = (abs(n) // d) * (-1 if n < 0 else 1)
    else:
        q, r = divmod(abs(n), d)
        if 2 * r > d or (2 * r == d and (fn == 'roundf' or q & 1)):
            q += 1
        result = q * (-1 if n < 0 else 1)
    rb = (raw & SIGN) if result == 0 else word(float(result))
    with gmpy2.context(precision=60, round=gmpy2.RoundToNearest):
        x = gmpy2.mpfr(value(raw))
        operation = {'floorf': gmpy2.rint_floor, 'ceilf': gmpy2.rint_ceil,
                     'truncf': gmpy2.rint_trunc, 'roundf': gmpy2.rint_round,
                     'rintf': gmpy2.rint}[fn]
        reference = operation(x)
        reference_bits = word(float(reference))
        if gmpy2.is_zero(reference) and gmpy2.is_signed(reference):
            reference_bits = SIGN
    if reference_bits != rb:
        raise RuntimeError('floatbasic Fraction/MPFR rounding disagreement for %s(%08x)' % (fn, raw))
    return rb


def certify_sqrt(raw, result):
    x = Fraction.from_float(value(raw))
    r = Fraction.from_float(value(result))
    low = (Fraction.from_float(value(result - 1)) + r) / 2
    high = (Fraction.from_float(value(result + 1)) + r) / 2
    low_square, high_square = low * low, high * high
    if x < low_square or x > high_square or ((x == low_square or x == high_square) and result & 1):
        raise RuntimeError('floatbasic sqrt exact midpoint-square certificate failed')


def sqrt_answer(raw):
    a = raw & ~SIGN
    if a > INF:
        return QNAN
    if a == 0:
        return raw
    if raw & SIGN:
        return QNAN
    if a == INF:
        return raw
    with gmpy2.context(precision=24, round=gmpy2.RoundToNearest,
                      emin=gmpy2.get_emin_min(), emax=gmpy2.get_emax_max()):
        reference = gmpy2.sqrt(gmpy2.mpfr(value(raw)))
    result = word(float(reference))
    certify_sqrt(raw, result)
    return result


def unary_answer(fn, raw):
    if fn == 'sqrtf':
        return sqrt_answer(raw)
    if fn == 'fabsf':
        return QNAN if (raw & ~SIGN) > INF else raw & ~SIGN
    return integer_answer(fn, raw)


def copy_answer(x, y):
    if (x & ~SIGN) > INF:
        return QNAN
    result = (x & ~SIGN) | (y & SIGN)
    if word(math.copysign(value(x), value(y))) != result:
        raise RuntimeError('floatbasic copy-sign bit/reference disagreement')
    return result


def self_check():
    cases = (('floorf', word(-0.25), word(-1.0)),
             ('floorf', SIGN, SIGN), ('ceilf', word(-0.25), SIGN),
             ('truncf', word(-0.75), SIGN),
             ('roundf', word(0.5), word(1.0)),
             ('roundf', word(-0.5), word(-1.0)),
             ('rintf', word(0.5), 0), ('rintf', word(-0.5), SIGN),
             ('rintf', word(1.5), word(2.0)),
             ('rintf', word(2.5), word(2.0)),
             ('fabsf', SIGN, 0), ('fabsf', QNAN | SIGN | 7, QNAN),
             ('sqrtf', word(4.0), word(2.0)),
             ('sqrtf', word(-1.0), QNAN), ('sqrtf', SIGN, SIGN),
             ('sqrtf', 1, 0x1a3504f3))
    for fn, raw, expected in cases:
        if unary_answer(fn, raw) != expected:
            raise RuntimeError('floatbasic oracle self-check failed: ' + fn)
    if copy_answer(word(3.0), INF | SIGN | 1) != word(-3.0):
        raise RuntimeError('floatbasic oracle self-check failed: sign-only y')
    if copy_answer(QNAN | 7, SIGN) != QNAN:
        raise RuntimeError('floatbasic oracle self-check failed: canonical x NaN')
    selected = sqrt_answer(word(2.0))
    try:
        certify_sqrt(word(2.0), selected + 1)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('floatbasic oracle self-check failed: sqrt certificate accepted wrong result')


def inputs(seed, count, fresh):
    rng = random.Random(seed)
    seen, words = set(), []

    def add(raw):
        if not (0 <= raw < (1 << 32)) or signaling(raw) or raw in seen:
            return
        seen.add(raw)
        words.append(raw)

    def signed_near(raw):
        for delta in (-1, 0, 1):
            if 0 <= raw + delta < INF:
                add(raw + delta)
                add((raw + delta) | SIGN)

    for raw in (0, SIGN, INF, INF | SIGN, INF - 1, (INF - 1) | SIGN,
                QNAN, QNAN | SIGN | 7, QNAN | (QUIET - 1)):
        add(raw)
    for e in range(1, 255, 8 if fresh else 1):
        for mantissa in (0, 1, 0x7fffff, rng.getrandbits(23)):
            add((e << 23) | mantissa)
            add(SIGN | (e << 23) | mantissa)
    for k in range(23):
        for raw in (1 << k, (1 << (k + 1)) - 1, rng.randrange(1, 1 << (k + 1))):
            add(raw)
            add(raw | SIGN)
    for n in range(0, 17 if fresh else 129):
        signed_near(word(n + 0.5))
        signed_near(word(float(n * n)))
    for x in (0.5, 1.0, 1.5, 2.5, 2.0 ** 22, 2.0 ** 23, 2.0 ** 24,
              value(0x00800000), value(0x007fffff), value(INF - 1)):
        signed_near(word(x))
    for e in (-74, -63, -1, 0, 1, 30, 63):
        for mantissa in (1.0, 1.5, 1.75, 1 + 2.0 ** -11):
            root = math.ldexp(mantissa, e)
            square = Fraction.from_float(root) ** 2
            try:
                raw = word(float(square))
            except OverflowError:
                continue
            if raw < INF:
                signed_near(raw)
    for _ in range(32 if fresh else 256):
        root = math.ldexp(1 + rng.getrandbits(23) * 2.0 ** -23, rng.randrange(-75, 64))
        root_bits = word(root)
        midpoint = (Fraction.from_float(root) + Fraction.from_float(value(root_bits + 1))) / 2
        try:
            raw = word(float(midpoint * midpoint))
        except OverflowError:
            continue
        if raw < INF:
            signed_near(raw)
    for _ in range(count):
        add(rng.getrandbits(32))
    return words


def copy_inputs(population, seed):
    rng = random.Random(seed ^ 0x7369676e)
    signs = (0, SIGN, INF, INF | SIGN, QNAN, QNAN | SIGN | 7)
    seen, pairs = set(), []
    def add(x, y):
        if signaling(x) or signaling(y) or (x, y) in seen:
            return
        seen.add((x, y))
        pairs.append((x, y))
    for i, x in enumerate(population):
        y = signs[i % len(signs)] if i % 3 == 0 else rng.getrandbits(32)
        if signaling(y):
            y |= QUIET
        add(x, y)
    for x in signs + (word(3.0), word(-3.0), 1, SIGN | 1):
        for y in signs:
            add(x, y)
    return pairs


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
    for fn in UNARY + ('copysignf',):
        rows = copy_inputs(population, args.seed) if fn == 'copysignf' else [(raw,) for raw in population]
        with (args.out / (fn + '.corpus')).open('w') as out:
            out.write('# Pinned oracle: tools/oracle/gen_corpus_floatbasic.py; MPFR %s gmpy2 %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version()))
            out.write('# seed %d count %d fresh %s entries %d\n' %
                      (args.seed, args.count, args.fresh, len(rows)))
            out.write('# binary32 inputs/results exactly widened to binary64 words\n')
            for raw_tuple in rows:
                result = copy_answer(*raw_tuple) if fn == 'copysignf' else unary_answer(fn, raw_tuple[0])
                out.write(' '.join('%016x' % wide(raw) for raw in raw_tuple + (result,)) + '\n')
        print('%s: %d entries' % (fn, len(rows)), flush=True)


if __name__ == '__main__':
    main()
