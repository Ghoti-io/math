#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned MPFR/mparithmetic oracle for log2, log10 and binary32 log2f.

Run via tools/oracle/oracle.py logbase|fresh-logbase, never using a host oracle.
Each row: binary64 input bits, binary64 result bits, binary32 signed error bits.
Float input/result words are exact widenings; errors use the TRUE binary32 ULP.
Expected results round the 600-bit MPFR rational directly to 24 or 53 bits,
never through a rounded binary64 intermediate for a binary32 expectation.
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


def value(u, single=False):
    return struct.unpack('>f' if single else '>d',
                         struct.pack('>I' if single else '>Q', u))[0]


def exponent(a):
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if a < Fraction(2) ** e:
        e -= 1
    return e


def rounded(fr, precision):
    """Round a rational straight to the requested IEEE significand precision."""
    if not fr:
        return 0.0, Fraction(0)
    a = abs(fr)
    emin = -126 if precision == 24 else -1022
    unit = Fraction(2) ** (max(exponent(a), emin) - precision + 1)
    scaled = a / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r > scaled.denominator or (2 * r == scaled.denominator and q & 1):
        q += 1
    rf = q * unit * (-1 if fr < 0 else 1)
    result = float(rf)
    if Fraction.from_float(result) != rf:
        raise RuntimeError('target result did not widen exactly')
    return result, (fr - rf) / unit


def exact(fn, x):
    with gmpy2.context(precision=600, emin=gmpy2.get_emin_min(),
                      emax=gmpy2.get_emax_max()):
        a = gmpy2.mpfr(x)
        return gmpy2.log10(a) if fn == 'log10' else gmpy2.log2(a)


def entry(fn, xb, precision):
    x = value(xb)
    ax = xb & ~SIGN
    special = None
    if ax > INF or (xb & SIGN and ax != 0):
        special = QNAN
    elif ax == 0:
        special = INF | SIGN
    elif ax == INF:
        special = INF
    elif x == 1:
        special = 0
    reference = exact(fn, x)
    if special is not None:
        if special == QNAN:
            agrees = reference.is_nan()
        elif special & ~SIGN == INF:
            agrees = gmpy2.is_infinite(reference) and ((reference < 0) == bool(special & SIGN))
        else:
            agrees = reference == 0
        if not agrees:
            raise RuntimeError('IEEE special rule disagrees with MPFR for %s(%016x)' % (fn, xb))
        return special, 0
    n, d = reference.as_integer_ratio()
    fr = Fraction(int(n), int(d))
    mp.prec = 640
    a = mp.mpf(x)
    independent = mp.log10(a) if fn == 'log10' else mp.log(a, 2)
    as_mp = mp.mpf(fr.numerator) / mp.mpf(fr.denominator)
    if abs(independent - as_mp) > abs(as_mp) * mp.mpf(2) ** -400:
        raise RuntimeError('MPFR and mpmath disagree for %s(%016x)' % (fn, xb))
    result, error = rounded(fr, precision)
    ebits = struct.unpack('>I', struct.pack('>f', float(error)))[0]
    return bits(result), ebits


def self_check():
    # These fixed IEEE words do not depend on the generated input population.
    for x, expected in ((1.0, 0.0), (2.0, 1.0), (0.5, -1.0),
                        (value(1), -1074.0), (value(0x7fe0000000000000), 1023.0)):
        if entry('log2', bits(x), 53) != (bits(expected), 0):
            raise RuntimeError('logbase oracle self-check failed: log2 binary power')
    for x, expected in ((1.0, 0.0), (10.0, 1.0), (100.0, 2.0), (1000.0, 3.0)):
        if entry('log10', bits(x), 53) != (bits(expected), 0):
            raise RuntimeError('logbase oracle self-check failed: log10 decimal power')
    midpoint = Fraction(1) + Fraction(2) ** -24
    # Just above a float midpoint but below binary64 resolution: double-rounding
    # would incorrectly choose 1.0 instead of the next binary32 value.
    cases = ((midpoint, 0x3ff0000000000000),
             (midpoint + Fraction(2) ** -80, 0x3ff0000020000000),
             (Fraction(1) + 3 * Fraction(2) ** -24, 0x3ff0000040000000),
             (-midpoint, 0xbff0000000000000),
             (-midpoint - Fraction(2) ** -80, 0xbff0000020000000),
             (-midpoint + Fraction(2) ** -80, 0xbff0000000000000),
             (-Fraction(2) + Fraction(2) ** -24, 0xc000000000000000),
             (-Fraction(2) + Fraction(2) ** -24 + Fraction(2) ** -80,
              0xbfffffffe0000000))
    for fr, expected in cases:
        if bits(rounded(fr, 24)[0]) != expected:
            raise RuntimeError('logbase oracle self-check failed: direct binary32 rounding')


def inputs(single, seed, count, fresh):
    width, fraction, expmax = (32, 23, 255) if single else (64, 52, 2047)
    sign = 1 << (width - 1)
    inf = expmax << fraction
    quiet = 1 << (fraction - 1)
    one = ((expmax - 1) // 2) << fraction
    rng = random.Random(seed + width * 1000003)
    seen = set()
    words = []

    def add(raw):
        if raw < 0 or raw >= (1 << width):
            return
        if single and (raw & ~sign) > inf and not (raw & quiet):
            return
        word = bits(value(raw, single))
        if word not in seen:
            seen.add(word)
            words.append(word)

    def near(raw):
        for delta in (-1, 0, 1):
            add(raw + delta)

    specials = [0, sign, inf, inf | sign, inf | quiet, inf | quiet | sign | 7,
                one | sign, inf - 1, (inf - 1) | sign]
    if not single:
        specials += [inf | 1, inf | sign | 1]
    for raw in specials:
        add(raw)
    low, high, bias = (-149, 127, 127) if single else (-1074, 1023, 1023)
    step = (4 if single else 16) if fresh else 1
    powers = set(range(low, high + 1, step)) | {low, low + 1, 1 - bias, -1, 0, 1, high}
    for e in sorted(powers):
        raw = ((e + bias) << fraction) if e >= 1 - bias else (1 << (e - low))
        near(raw)
    for k in range(fraction):
        near(1 << k)
        add((1 << (k + 1)) - 1)
    # log_front's normalized table boundaries, exactly projected to the target
    # input format, and their immediate neighbors in that format.
    for j in range(129):
        d = value(0x3fe6a00000000000 + (j << 45))
        raw = struct.unpack('>I', struct.pack('>f', d))[0] if single else bits(d)
        near(raw)
    for offset in range(-(64 if fresh else 512), (64 if fresh else 512) + 1):
        add(one + offset)
    decimal_low, decimal_high = (-45, 38) if single else (-323, 308)
    for e in range(decimal_low, decimal_high + 1, 8 if fresh else 1):
        d = float(Fraction(10) ** e)
        raw = struct.unpack('>I', struct.pack('>f', d))[0] if single else bits(d)
        near(raw)
    for _ in range(64 if fresh else 256):
        add(rng.getrandbits(fraction))
    for _ in range(count):
        raw = rng.getrandbits(width - 1)
        if raw < inf:
            add(raw)
    for _ in range(32 if fresh else 100):
        add((rng.randrange(1, inf)) | sign)
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
    args.out.mkdir(parents=True, exist_ok=True)
    provenance = 'MPFR %s gmpy2 %s mpmath %s' % (gmpy2.mpfr_version(), gmpy2.version(), mpmath.__version__)
    for single in (False, True):
        population = inputs(single, args.seed, args.count, args.fresh)
        for fn in (('log2f',) if single else ('log2', 'log10')):
            with (args.out / (fn + '.corpus')).open('w') as out:
                out.write('# Pinned oracle: tools/oracle/gen_corpus_logbase.py; %s\n' % provenance)
                out.write('# seed %d count %d fresh %s entries %d\n' % (args.seed, args.count, args.fresh, len(population)))
                out.write('# x_bits r_bits err_bits; float values widened; err uses target-format ULP\n')
                for xb in population:
                    rb, eb = entry(fn, xb, 24 if single else 53)
                    out.write('%016x %016x %08x\n' % (xb, rb, eb))
            print('%s: %d entries' % (fn, len(population)), flush=True)


if __name__ == '__main__':
    main()
