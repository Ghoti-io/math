#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact modf pairs: independent Fraction truncation versus pinned MPFR.

Special-value bits and exception classes use the documented library contract.
No implementation source is inspected. Publication reuses the exception-rollback
publisher; a multi-file generation is not crash-atomic.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import random
import struct
import gmpy2
from gen_corpus_float_scale import publish_set


def bits(v, width):
    return struct.unpack('>Q' if width == 64 else '>I',
                         struct.pack('>d' if width == 64 else '>f', v))[0]


def value(raw, width):
    return struct.unpack('>d' if width == 64 else '>f',
                         raw.to_bytes(width//8, 'big'))[0]


def expected(raw, width):
    p, bias, eb = (52, 1023, 11) if width == 64 else (23, 127, 8)
    sign = raw & (1 << (width-1)); a = raw ^ sign
    infinity = ((1 << eb)-1) << p; quiet = 1 << (p-1)
    if a > infinity:
        return infinity | quiet, infinity | quiet, int(not a & quiet)
    if a == infinity:
        return sign, raw, 0
    exponent, mantissa = divmod(a, 1 << p)
    if exponent: mantissa += 1 << p
    power = (exponent or 1)-bias-p
    q = Fraction(mantissa << power) if power >= 0 else Fraction(mantissa, 1 << -power)
    if sign: q = -q
    integer = int(q); fraction = q-integer
    i = bits(float(integer), width) if integer else sign
    f = bits(float(fraction), width) if fraction else sign
    # MPFR independently truncates a binary value, then subtracts exactly.
    with gmpy2.context(precision=1200, emin=-100000, emax=100000):
        x = gmpy2.mpfr(value(raw, width))
        whole = gmpy2.trunc(x)
        part = x-whole
        mi = bits(float(whole), width) if whole else sign
        mf = bits(float(part), width) if part else sign
    if (f, i) != (mf, mi):
        raise RuntimeError('Fraction/MPFR split disagreement: %x' % raw)
    if Fraction(value(f, width)) != fraction or Fraction(value(i, width)) != integer:
        raise RuntimeError('split output not exactly representable')
    return f, i, 0


def population(width, seed, count):
    p, bias, eb = (52,1023,11) if width == 64 else (23,127,8)
    sign = 1 << (width-1); inf = ((1 << eb)-1) << p
    words = {0, 1, 2, (1 << p)-1, 1 << p, inf-1, inf, inf+1,
             inf+(1 << (p-1))-1, inf+(1 << (p-1)), inf+(1 << (p-1))+1, sign-1}
    # Every binade and edge significands, plus every mask endpoint.
    for exponent in range((1 << eb)-1):
        for sig in (0, 1, 2, (1 << (p-1))-1, 1 << (p-1), (1 << p)-2, (1 << p)-1):
            words.add((exponent << p)|sig)
    for e in range(p):
        for integer in (1, 3, 7, 13):
            center = bits(float(integer * (1 << e)), width)
            words.update(center+d for d in (-2,-1,0,1,2))
    words |= {v|sign for v in tuple(words)}
    rng = random.Random(seed ^ width)
    words.update(rng.getrandbits(width) for _ in range(count))
    return sorted(words)


def feed(h, value):
    for byte in value.to_bytes(8,'little'):
        h = ((h ^ byte)*0x100000001b3) & ((1 << 64)-1)
    return h


def reference_hash(rows,width):
    h = state = 0xcbf29ce484222325; calls = 0
    inf = 0x7ff0000000000000 if width == 64 else 0x7f800000
    sign = 1 << (width-1)
    for n,(raw,f,i,flags) in enumerate(rows,1):
        h = feed(feed(h,f),i)
        sets = 32 if n%61 == 0 or raw & (sign-1) >= inf else 1
        for _ in range(4*sets*2):
            state = feed(feed(feed(state,f),i),f)
        calls += 16*sets
    return '%016x %d state %016x %d' % (h,len(rows),state,calls)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20261027)
    ap.add_argument('--count', type=int, default=2000)
    ap.add_argument('--fresh', action='store_true'); a = ap.parse_args()
    if not 0 <= a.count <= 200000 or not 0 <= a.seed < 1 << 64:
        ap.error('count must be 0..200000 and seed unsigned64')
    known = [(64,0xbff8000000000000,0xbfe0000000000000,0xbff0000000000000,0),
             (32,0xbf800001,0xb4000000,0xbf800000,0),
             (64,0xfff0000000000000,0x8000000000000000,0xfff0000000000000,0),
             (32,0x7f800001,0x7fc00000,0x7fc00000,1),
             (64,0xc000000000000000,0x8000000000000000,0xc000000000000000,0),
             (32,0x80000001,0x80000001,0x80000000,0),
             (32,0x80000000,0x80000000,0x80000000,0)]
    for width,raw,f,i,flags in known:
        if expected(raw,width) != (f,i,flags):
            raise RuntimeError('fixed split oracle control failed')
    if gmpy2.version() != '2.3.2' or gmpy2.mpfr_version().split()[-1] != '4.2.2':
        raise RuntimeError('split generator requires pinned MPFR4.2.2/gmpy2 2.3.2')
    payloads = {}; hashes = []
    for width in (64,32):
        rows = [(raw,*expected(raw,width)) for raw in population(width,a.seed,a.count)]
        name = 'modf' if width == 64 else 'modff'
        hashes.append('split.%s %s\n' % (name,reference_hash(rows,width)))
        header = '# Pinned oracle: fraction_split MPFR 4.2.2 gmpy2 2.3.2\n# function %s\n# seed %d count %d fresh %s entries %d\n' % (name,a.seed,a.count,a.fresh,len(rows))
        payloads[name+'-special.corpus'] = header+'# input fraction integral invalid\n'+''.join(('%0*x %0*x %0*x %d\n' % (width//4,x,width//4,f,width//4,i,flags)) for x,f,i,flags in rows)
        # Generic result-hash tool consumes unary widened input; signaling Float
        # arguments are excluded because its double-to-Float cast could quiet.
        widened = []
        for x,f,i,flags in rows:
            if width == 32 and flags: continue
            def wide(raw):
                # Canonical output NaNs stay canonical in binary64.
                v = value(raw,width)
                return bits(v,64) if v == v else 0x7ff8000000000000
            widened.append((wide(x),wide(f),wide(i)))
        for index,part in ((1,'fraction'),(2,'integral')):
            payloads[name+'_'+part+'.corpus'] = header.replace('entries %d' % len(rows), 'entries %d' % len(widened))+''.join('%016x %016x\n'%(r[0],r[index]) for r in widened)
        print('%s: %d raw; %d widened rows' % (name,len(rows),len(widened)),flush=True)
    payloads['fraction_split-special.hash'] = ''.join(hashes)
    a.out.mkdir(parents=True,exist_ok=True)
    publish_set(a.out,payloads)


if __name__ == '__main__': main()
