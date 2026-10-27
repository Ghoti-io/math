#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact min/max corpora from rational comparison and explicit IEEE rules.

Three binary64 words encode the inputs and result. Binary32 inputs/results
are widened exactly; binary32 signaling NaNs are excluded because widening
quiets them (raw-bit unit tests cover signaling NaNs separately).
"""
import argparse
from fractions import Fraction
from pathlib import Path
import random
import struct

SIGN = 0x8000000000000000
INF = 0x7ff0000000000000
QUIET = 0x0008000000000000
QNAN = INF | QUIET


def bits(x):
    return struct.unpack('>Q', struct.pack('>d', x))[0]


def value(u, single=False):
    return struct.unpack('>f' if single else '>d',
                         struct.pack('>I' if single else '>Q', u))[0]


def answer(x, y, minimum):
    ax, ay = x & ~SIGN, y & ~SIGN
    xn, yn = ax > INF, ay > INF
    if (xn and not (ax & QUIET)) or (yn and not (ay & QUIET)):
        return QNAN
    if xn:
        return QNAN if yn else y
    if yn:
        return x
    if ax == 0 and ay == 0:
        return (x | y) if minimum else (x & y)
    if x == y:
        return x
    if ax == INF or ay == INF:
        # Infinity has no Fraction representation; its ordering is explicit.
        x_less = (ax == INF and bool(x & SIGN)) or (ay == INF and not (y & SIGN))
    else:
        x_less = Fraction.from_float(value(x)) < Fraction.from_float(value(y))
    return x if x_less == minimum else y


def self_check():
    cases = (
        (0, SIGN, SIGN, 0),
        (SIGN, 0, SIGN, 0),
        (0x3ff0000000000000, 0xbff0000000000000,
         0xbff0000000000000, 0x3ff0000000000000),
        (QNAN | 7, 0x3ff0000000000000, 0x3ff0000000000000, 0x3ff0000000000000),
        (0x3ff0000000000000, QNAN | 7, 0x3ff0000000000000, 0x3ff0000000000000),
        (QNAN | 7, QNAN | SIGN | 3, QNAN, QNAN),
        (INF | 1, 0x3ff0000000000000, QNAN, QNAN),
        (QNAN, INF | 1, QNAN, QNAN),
        (INF, INF | SIGN, INF | SIGN, INF),
        (INF, 0x3ff0000000000000, 0x3ff0000000000000, INF),
        (1, SIGN | 1, SIGN | 1, 1),
        (0x3ff0000000000000, 0x4000000000000000,
         0x3ff0000000000000, 0x4000000000000000),
        (0xbff0000000000000, 0xc000000000000000,
         0xc000000000000000, 0xbff0000000000000),
        (0x3ff0000000000000, 0x3ff0000000000001,
         0x3ff0000000000000, 0x3ff0000000000001),
        (0xbff0000000000000, 0xbff0000000000001,
         0xbff0000000000001, 0xbff0000000000000),
        (1, 2, 1, 2),
        (SIGN | 1, SIGN | 2, SIGN | 2, SIGN | 1),
    )
    for x, y, low, high in cases:
        for minimum, expected in ((True, low), (False, high)):
            actual = answer(x, y, minimum)
            if actual != expected:
                raise RuntimeError('extrema oracle self-check failed: '
                                   '%016x %016x minimum=%s: %016x != %016x' %
                                   (x, y, minimum, actual, expected))


def inputs(single, seed, count):
    width, fraction, expmax = (32, 23, 255) if single else (64, 52, 2047)
    sign = 1 << (width - 1)
    hidden = 1 << fraction
    inf = expmax << fraction
    quiet = hidden >> 1
    one = ((expmax - 1) // 2) << fraction
    rng = random.Random(seed + width * 1000003)
    seen = set()

    def add(x, y):
        if single:
            # Float signaling NaN status cannot survive widening.
            for raw in (x, y):
                if (raw & ~sign) > inf and not (raw & quiet):
                    return []
        pair = bits(value(x, single)), bits(value(y, single))
        if pair in seen:
            return []
        seen.add(pair)
        return [pair]

    specials = [0, sign, one, sign | one, 1, sign | 1, inf - 1,
                sign | (inf - 1), inf, sign | inf, inf | quiet | 7,
                sign | inf | quiet | 3]
    if not single:
        specials += [inf | 1, sign | inf | 1]
    for x in specials:
        for y in specials:
            yield from add(x, y)
    for e in range(1, expmax):
        x = (e << fraction) | rng.getrandbits(fraction)
        yield from add(x | (sign if e & 1 else 0), one)
        yield from add(one | sign, x | (sign if e & 1 else 0))
        yield from add((e << fraction) | (hidden - 1), (e << fraction))
        # Neighboring encodings across every exponent boundary, both signs
        # and both argument orders. e=1 crosses subnormal/normal.
        low, high = (e << fraction) - 1, e << fraction
        for signed in (0, sign):
            yield from add(low | signed, high | signed)
            yield from add(high | signed, low | signed)
        if e % 16 == 0:
            # Close same-sign values inside a binade as well as its boundary.
            for signed in (0, sign):
                yield from add(x | signed, (x + 1) | signed)
                yield from add((x + 1) | signed, x | signed)
    for k in range(fraction):
        for x in (1 << k, (1 << (k + 1)) - 1):
            yield from add(x, x | sign)
            yield from add(x | sign, x)
    for k in range(fraction):
        low, high = 1 << k, (1 << k) + 1
        for signed in (0, sign):
            yield from add(low | signed, high | signed)
            yield from add(high | signed, low | signed)
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
        pairs = list(inputs(single, args.seed, args.count))
        for minimum in (True, False):
            name = ('fmin' if minimum else 'fmax') + ('f' if single else '')
            with (args.out / (name + '.corpus')).open('w') as out:
                out.write('# Exact rational/IEEE oracle: tools/oracle/gen_corpus_extrema.py\n')
                out.write('# seed %d random-count %d entries %d\n' % (args.seed, args.count, len(pairs)))
                out.write('# x_bits y_bits result_bits (binary64; binary32 widened for float)\n')
                for x, y in pairs:
                    result = answer(x, y, minimum)
                    if single and result != QNAN:
                        narrowed = struct.unpack('>f', struct.pack('>f', value(result)))[0]
                        if bits(narrowed) != result:
                            raise RuntimeError('binary32 extrema must be exactly representable')
                    out.write('%016x %016x %016x\n' % (x, y, result))
            print('%s: %d entries' % (name, len(pairs)))


if __name__ == '__main__':
    main()
