#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact fmod/fmodf corpora from rational arithmetic (Python standard library).

All three columns contain binary64 words; fmodf inputs and results are exact
widenings of binary32 numbers. NaN answers use the canonical binary64 NaN.
The reference computes x - trunc(x/y)*y in unbounded rational arithmetic,
independently of the implementation's significand reduction. It never calls
host fmod. --count controls the additional random pairs per format.
"""
import argparse
from fractions import Fraction
import math
from pathlib import Path
import random
import struct

QNAN = 0x7ff8000000000000


def bits(x):
    return struct.unpack('>Q', struct.pack('>d', x))[0]


def value(u, single=False):
    return struct.unpack('>f' if single else '>d',
                         struct.pack('>I' if single else '>Q', u))[0]


def answer(ux, uy):
    x, y = value(ux), value(uy)
    if math.isnan(x) or math.isnan(y) or math.isinf(x) or y == 0:
        return QNAN
    if math.isinf(y) or x == 0:
        return ux
    a, b = Fraction.from_float(x), Fraction.from_float(y)
    ratio = a / b
    n = abs(ratio.numerator) // ratio.denominator
    if ratio < 0:
        n = -n
    remainder = a - n * b
    if not remainder:
        return ux & (1 << 63)
    result = float(remainder)
    assert Fraction.from_float(result) == remainder, 'remainder must be exact'
    return bits(result)


def self_check():
    """Fixed IEEE answers independently pin the rational reference's meaning."""
    cases = (
        (0x4016000000000000, 0x4000000000000000, 0x3ff8000000000000),
        (0xc016000000000000, 0xc000000000000000, 0xbff8000000000000),
        (0x0010000000000001, 0x0010000000000000, 0x0000000000000001),
        (0x7fe0000000000000, 0x0000000000000003, 0x0000000000000002),
        (0x7ff8000000000007, 0x0000000000000000, 0x7ff8000000000000),
        (0x8000000000000000, 0x4000000000000000, 0x8000000000000000),
        (0x3ff0000000000000, 0x7ff0000000000000, 0x3ff0000000000000),
    )
    for x, y, expected in cases:
        actual = answer(x, y)
        if actual != expected:
            raise RuntimeError('remainder oracle self-check failed: '
                               '%016x %% %016x: %016x != %016x' %
                               (x, y, actual, expected))


def inputs(single, seed, count):
    width, fraction, expmax = (32, 23, 255) if single else (64, 52, 2047)
    sign = 1 << (width - 1)
    hidden = 1 << fraction
    inf = expmax << fraction
    largest = inf - 1
    one = ((expmax - 1) // 2) << fraction
    rng = random.Random(seed + width * 1000003)
    seen = set()

    def add(x, y):
        pair = bits(value(x, single)), bits(value(y, single))
        if pair not in seen:
            seen.add(pair)
            return [pair]
        return []

    specials = [0, sign, one, sign | one, 1, sign | 1, largest,
                sign | largest, inf, sign | inf, inf | (hidden >> 1),
                sign | inf | (hidden >> 1) | 7]
    for x in specials:
        for y in specials:
            yield from add(x, y)
    # Exercise every normal exponent in both operand positions, across signs,
    # with maximal significands, unit significands, and large exponent gaps.
    for e in range(1, expmax):
        x = (e << fraction) | rng.getrandbits(fraction)
        yield from add(x | (sign if e & 1 else 0), one | 3)
        yield from add(largest, x | (sign if e & 1 else 0))
        yield from add((e << fraction) | (hidden - 1), 1)
    # Every subnormal bit length and immediate neighbors of the normal boundary.
    for k in range(fraction):
        for x in (1 << k, (1 << (k + 1)) - 1):
            yield from add(x | sign, 3)
            yield from add(largest, x)
    for x in (hidden - 1, hidden, hidden + 1, largest):
        for y in (1, 3, hidden - 1, hidden, hidden + 1):
            yield from add(x, y)
    # Exact multiples and their two adjacent values, including negative signs.
    for _ in range(250):
        y = rng.randint(1, 1000)
        x = y * rng.randint(1, 1000)
        ux = bits(float(x)) if not single else struct.unpack('>I', struct.pack('>f', float(x)))[0]
        uy = bits(float(y)) if not single else struct.unpack('>I', struct.pack('>f', float(y)))[0]
        for delta in (-1, 0, 1):
            yield from add((ux + delta) | (sign if rng.getrandbits(1) else 0), uy)
    for _ in range(count):
        yield from add(rng.getrandbits(width), rng.getrandbits(width))


def main():
    self_check()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=20261026)
    parser.add_argument('--count', type=int, default=3000)
    args = parser.parse_args()
    if args.count < 0:
        parser.error('--count must be nonnegative')
    args.out.mkdir(parents=True, exist_ok=True)
    for single in (False, True):
        name = 'fmodf' if single else 'fmod'
        pairs = list(inputs(single, args.seed, args.count))
        with (args.out / (name + '.corpus')).open('w') as out:
            out.write('# Exact rational oracle: tools/oracle/gen_corpus_remainder.py\n')
            out.write('# seed %d random-count %d entries %d\n' % (args.seed, args.count, len(pairs)))
            out.write('# x_bits y_bits result_bits (binary64; binary32 widened for fmodf)\n')
            for x, y in pairs:
                result = answer(x, y)
                if single and result != QNAN:
                    narrowed = struct.unpack('>f', struct.pack('>f', value(result)))[0]
                    if bits(narrowed) != result:
                        raise RuntimeError('binary32 remainder must be exactly representable')
                out.write('%016x %016x %016x\n' % (x, y, result))
        print('%s: %d entries' % (name, len(pairs)))


if __name__ == '__main__':
    main()
