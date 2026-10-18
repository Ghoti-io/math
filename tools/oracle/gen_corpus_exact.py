#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
#
# Copyright (C) 2026 Corey Pennycuff
#
# This file is part of Ghoti.io Math.
#
# Ghoti.io Math is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
"""Write the corpus files of the functions that have one correct answer: gmath_sqrt,
gmath_floor, gmath_ceil, gmath_trunc, gmath_round, gmath_rint, gmath_fabs,
gmath_copysign, gmath_scalbn, gmath_frexp and gmath_ilogb.

Runs in the pinned oracle image (tools/oracle/oracle.py corpus|fresh), after
gen_corpus.py and gen_corpus_elem.py.  These functions are not "within an
error" of anything: the result is exactly the answer, so a line of <fn>.corpus
is the arguments and the answer, hexadecimal and fixed width, and the test
requires the library's result to equal it bit for bit:

    sqrt floor ceil trunc round rint fabs   x_bits  r_bits
    copysign                                x_bits  y_bits  r_bits
    scalbn                                  x_bits  n (64 bits, sign extended)  r_bits
    frexp                                   x_bits  fraction_bits  e (64 bits, sign extended)
    ilogb                                   x_bits  n (64 bits, sign extended)

Every NaN result is r = 7ff8000000000000 (the library's one NaN), a NaN argument
of any sign and payload, quiet or signalling, giving it.  The sign of a zero
result is part of the answer.

How each answer is made, and what it is checked against (the run fails if two
disagree):

  sqrt      MPFR's correctly rounded square root (53 bits, round to nearest), and
            an integer square root of the significand with a remainder test
            written here (math.isqrt)
  floor ceil trunc round rint
            MPFR (gmpy2.rint_floor, rint_ceil, rint_trunc, rint_round (half away) and rint
            with round to nearest even), and exact rational arithmetic written here; the sign of a zero
            result is taken from C99 Annex F written out here (floor(-0) = -0,
            ceil(x) = -0 for -1 < x < 0, trunc, round and rint keep the sign of x)
  scalbn    MPFR mul_2exp with the exponent range and the subnormals of binary64,
            and exact rationals rounded once by Python's correctly rounded int / int
  frexp     exact: the fraction times 2^e is x
  ilogb     exact: floor(log2 |x|) from the rational value
  fabs copysign
            the sign bit, by integer operations

The inputs, by function (see the functions below for the details):

  sqrt      the specials and the negative numbers; every exponent, with the
            mantissas 0, 1, all ones and random ones; every subnormal bit length;
            exact squares and their neighbours (the doubles each side of m^2);
            the doubles each side of (y + u/2)^2, the squares of the halfway
            points between two doubles, which are as close to a rounding
            boundary as a square root gets; powers of 4 and 2 and their
            neighbours; uniform bit patterns and uniform values
  rounding  the specials and the zeros; k + {0, 1/4, 1/2, 3/4} and the doubles each
            side of them for small k; every exponent with mantissas 0, 1, all
            ones; the halfway cases n + 1/2 for even and odd n up to 2^52; the
            doubles around 2^52 and 2^53; 1 - ulp, 1/2 +- ulp; subnormals; uniform
            and log-uniform values of both signs
  scalbn    the specials, zero, one, the extremes; n at the overflow, the
            underflow, the subnormal and the INT_MIN / INT_MAX edges; results
            half way between two subnormals (the tie to even and the tie past it);
            uniform exponents
  frexp, ilogb
            the specials, powers of two and their neighbours, every subnormal
            bit length, uniform bit patterns
"""

import argparse
import math
import os
import random
import struct
import sys
from fractions import Fraction

import gmpy2
import mpmath
from mpmath import mp

EMIN = gmpy2.get_emin_min()
EMAX = gmpy2.get_emax_max()
INF = math.inf
QNAN_BITS = 0x7FF8000000000000
DBL_MAX = sys.float_info.max
DBL_MIN = sys.float_info.min
DENORM_MIN = 5e-324
INT_MIN = -(1 << 31)
INT_MAX = (1 << 31) - 1
M64 = (1 << 64) - 1


def bits_of(d):
    return struct.unpack(">Q", struct.pack(">d", d))[0]


def double_of(u):
    return struct.unpack(">d", struct.pack(">Q", u))[0]


def is_nan_bits(u):
    return (u & 0x7FFFFFFFFFFFFFFF) > 0x7FF0000000000000


def frac_of(u):
    """The exact value of a finite double, from its bits."""
    s = -1 if u >> 63 else 1
    e = (u >> 52) & 0x7FF
    m = u & ((1 << 52) - 1)
    if e == 0:
        return s * Fraction(m, 1) * Fraction(2) ** -1074
    return s * Fraction((1 << 52) | m, 1) * Fraction(2) ** (e - 1075)


def round_to_double(fr):
    """The correctly rounded (nearest even) double of a rational, with overflow to
    infinity and underflow to zero, by Python's correctly rounded int / int."""
    if fr == 0:
        return 0.0
    sign = 1 if fr > 0 else -1
    a = abs(fr)
    if a >= Fraction(2) ** 1024 - Fraction(2) ** 970:
        return sign * INF
    if a <= Fraction(2) ** -1075:
        return math.copysign(0.0, sign)
    return sign * (a.numerator / a.denominator)


def int_hex(n):
    return "%016x" % (n & M64)


# ---------------------------------------------------------------------------
# The answers
# ---------------------------------------------------------------------------

def sqrt_answer(u):
    """(r_bits) for sqrt of the double with bits u, from MPFR, checked by an integer square root."""
    if is_nan_bits(u):
        return QNAN_BITS
    neg = u >> 63
    mag = u & 0x7FFFFFFFFFFFFFFF
    if mag == 0:
        return u
    if neg:
        return QNAN_BITS
    if mag == 0x7FF0000000000000:
        return mag
    x = double_of(u)
    with gmpy2.context(precision=53, emin=EMIN, emax=EMAX, round=gmpy2.RoundToNearest):
        r = float(gmpy2.sqrt(gmpy2.mpfr(x)))
    # an independent statement: the integer square root of the scaled significand, with its remainder
    fr = frac_of(u)
    num, den = fr.numerator, fr.denominator
    k = 640                                      # 4^k fr is at least 2^206: the root has 100+ bits
    scaled = num << (2 * k)
    rad = scaled // den                          # floor(fr 4^k); den is a power of two
    root = math.isqrt(rad)                       # floor(sqrt(fr) 2^k)
    sticky = (scaled % den != 0) or (root * root != rad)
    nb = root.bit_length()
    drop = nb - 53
    q = root >> drop
    rem = root & ((1 << drop) - 1)
    half = 1 << (drop - 1)
    if rem > half or (rem == half and (sticky or (q & 1))):
        q += 1
    r2 = float(Fraction(q) * Fraction(2) ** (drop - k))
    if bits_of(r) != bits_of(r2):
        raise SystemExit("sqrt(%016x): MPFR says %r, the integer square root %r" % (u, r, r2))
    # and a third, mpmath at 640 bits
    mp.prec = 640
    w = mp.sqrt(mp.mpf(Fraction(frac_of(u)).numerator) / mp.mpf(Fraction(frac_of(u)).denominator))
    d = abs(w - mp.mpf(Fraction(r).numerator) / mp.mpf(Fraction(r).denominator))
    ulp = Fraction(2) ** (math.frexp(r)[1] - 53)
    if d > mp.mpf(ulp.numerator) / mp.mpf(ulp.denominator) * mp.mpf("0.5000001"):
        raise SystemExit("sqrt(%016x): mpmath is farther than half an ulp from %r" % (u, r))
    return bits_of(r)


def round_answer(fn, u):
    if is_nan_bits(u):
        return QNAN_BITS
    sign = u >> 63
    mag = u & 0x7FFFFFFFFFFFFFFF
    if mag == 0x7FF0000000000000:
        return u
    x = double_of(u)
    fr = frac_of(u)
    if fn == "floor":
        v = math.floor(fr)
    elif fn == "ceil":
        v = math.ceil(fr)
    elif fn == "trunc":
        v = math.trunc(fr)
    elif fn == "round":
        v = math.floor(abs(fr) + Fraction(1, 2)) * (1 if fr >= 0 else -1)
    elif fn == "rint":
        a = abs(fr)
        f = math.floor(a)
        d = a - f
        if d > Fraction(1, 2) or (d == Fraction(1, 2) and f % 2 == 1):
            f += 1
        v = f * (1 if fr >= 0 else -1)
    else:
        raise SystemExit("unknown " + fn)
    r = float(v)
    if r == 0:
        # C99 Annex F: floor(-0) = -0, and a floor of 0 < x < 1 is +0; ceil(x) = -0 for -1 < x < 0;
        # trunc, round and rint keep the sign of x
        negative_zero = bool(sign) if fn != "floor" else (bool(sign) and mag == 0)
        r = -0.0 if negative_zero else 0.0
    ru = bits_of(r)
    # MPFR
    with gmpy2.context(precision=60, emin=EMIN, emax=EMAX, round=gmpy2.RoundToNearest):
        mx = gmpy2.mpfr(x)
        if fn == "floor":
            m = gmpy2.rint_floor(mx)
        elif fn == "ceil":
            m = gmpy2.rint_ceil(mx)
        elif fn == "trunc":
            m = gmpy2.rint_trunc(mx)
        elif fn == "round":
            m = gmpy2.rint_round(mx)
        else:
            m = gmpy2.rint(mx)
        mf = float(m)
        mu = bits_of(mf)
        if gmpy2.is_zero(m) and gmpy2.is_signed(m):
            mu = bits_of(-0.0)
    if mu != ru:
        raise SystemExit("%s(%016x): MPFR %016x, exact rationals %016x" % (fn, u, mu, ru))
    return ru


def scalbn_answer(u, n):
    if is_nan_bits(u):
        return QNAN_BITS
    mag = u & 0x7FFFFFFFFFFFFFFF
    if mag == 0 or mag == 0x7FF0000000000000:
        return u
    kk = max(-5000, min(5000, n))
    fr = frac_of(u) * Fraction(2) ** kk
    r = round_to_double(fr)
    if r == 0:
        r = math.copysign(0.0, -1.0 if u >> 63 else 1.0)
    ru = bits_of(r)
    with gmpy2.context(precision=53, emin=-1073, emax=1024, subnormalize=True, round=gmpy2.RoundToNearest):
        m = gmpy2.mul_2exp(gmpy2.mpfr(double_of(u)), kk)
        if gmpy2.is_infinite(m):
            mu = bits_of(math.copysign(INF, -1.0 if u >> 63 else 1.0))
        elif gmpy2.is_zero(m):
            mu = bits_of(math.copysign(0.0, -1.0 if u >> 63 else 1.0))
        else:
            mu = bits_of(float(m))
    if mu != ru:
        raise SystemExit("scalbn(%016x, %d): MPFR %016x, rationals %016x" % (u, n, mu, ru))
    return ru


def frexp_answer(u):
    if is_nan_bits(u):
        return QNAN_BITS, 0
    mag = u & 0x7FFFFFFFFFFFFFFF
    if mag == 0 or mag == 0x7FF0000000000000:
        return u, 0
    fr = frac_of(u)
    a = abs(fr)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    # a in [2^(e-1), 2^(e+1)); want a / 2^e' in [1/2, 1)
    if a < Fraction(2) ** (e - 1):
        e -= 1
    # now 2^(e-1) <= a < 2^e ?
    while a >= Fraction(2) ** e:
        e += 1
    while a < Fraction(2) ** (e - 1):
        e -= 1
    f = fr / Fraction(2) ** e
    assert Fraction(1, 2) <= abs(f) < 1
    mf, me = math.frexp(double_of(u))
    if me != e or Fraction(mf) != f:
        raise SystemExit("frexp(%016x): python %r %d, exact %s %d" % (u, mf, me, f, e))
    return bits_of(float(f)), e


def ilogb_answer(u):
    mag = u & 0x7FFFFFFFFFFFFFFF
    if mag > 0x7FF0000000000000:
        return INT_MAX
    if mag == 0x7FF0000000000000:
        return INT_MAX
    if mag == 0:
        return INT_MIN
    a = abs(frac_of(u))
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while a >= Fraction(2) ** (e + 1):
        e += 1
    while a < Fraction(2) ** e:
        e -= 1
    mf, me = math.frexp(double_of(u))
    if me - 1 != e:
        raise SystemExit("ilogb(%016x): python %d, exact %d" % (u, me - 1, e))
    return e


def fabs_answer(u):
    if is_nan_bits(u):
        return QNAN_BITS
    r = u & 0x7FFFFFFFFFFFFFFF
    assert bits_of(math.fabs(double_of(u))) == r
    return r


def copysign_answer(u, v):
    if is_nan_bits(u):
        return QNAN_BITS
    r = (u & 0x7FFFFFFFFFFFFFFF) | (v & (1 << 63))
    assert bits_of(math.copysign(double_of(u), double_of(v))) == r
    return r


# ---------------------------------------------------------------------------
# The inputs
# ---------------------------------------------------------------------------

class Bits:
    """An ordered, duplicate-free list of tuples of ints."""

    def __init__(self):
        self.seen = set()
        self.items = []

    def add(self, *args):
        if args not in self.seen:
            self.seen.add(args)
            self.items.append(args)


SPECIAL_BITS = [
    0x0000000000000000, 0x8000000000000000, 0x7FF0000000000000, 0xFFF0000000000000,
    0x7FF8000000000000, 0xFFF8000000000000, 0x7FF4000000000000, 0xFFF4000000000000,
    0x7FF0000000000001, 0xFFF0000000000001, 0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF,
    0x7FF8000000000001, 0x7FFC000000000000,
    0x0000000000000001, 0x8000000000000001, 0x000FFFFFFFFFFFFF, 0x800FFFFFFFFFFFFF,
    0x0010000000000000, 0x8010000000000000, 0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF,
    0x3FF0000000000000, 0xBFF0000000000000, 0x4000000000000000, 0xC000000000000000,
    0x3FE0000000000000, 0xBFE0000000000000, 0x3FD0000000000000,
]


def around_bits(u, n):
    """u and the n bit patterns each side of it, as the doubles' neighbours of the same sign."""
    out = [u]
    for k in range(1, n + 1):
        for v in (u + k, u - k):
            if 0 <= v <= 0xFFFFFFFFFFFFFFFF:
                out.append(v)
    return out


def rnd_bits(rng, lo_exp=0, hi_exp=2046, signed=True):
    e = rng.randint(lo_exp, hi_exp)
    m = rng.getrandbits(52)
    s = (rng.getrandbits(1) << 63) if signed else 0
    return s | (e << 52) | m


def sqrt_inputs(rng, size):
    I = Bits()
    for u in SPECIAL_BITS:
        I.add(u)
    for u in (0x8000000000000001, 0xBFF0000000000000, 0xFFEFFFFFFFFFFFFF, 0x8010000000000000, 0xC000000000000000):
        I.add(u)
    # every exponent
    for e in range(0, 2047):
        for m in (0, 1, 2, (1 << 52) - 1, (1 << 52) - 2, 1 << 51, (1 << 51) - 1, 0x5555555555555, 0xAAAAAAAAAAAAA):
            I.add((e << 52) | (m & ((1 << 52) - 1)))
        for _ in range(size["sqrt_per_exp"]):
            I.add((e << 52) | rng.getrandbits(52))
    # subnormals: every bit length
    for k in range(1, 53):
        for _ in range(size["sqrt_sub"]):
            I.add(rng.getrandbits(k) | (1 << (k - 1)))
        I.add(1 << (k - 1))
    # exact squares and their neighbours
    for _ in range(size["sqrt_exact"]):
        m = rng.getrandbits(rng.randint(1, 26)) | 1
        sq = m * m
        e = rng.randint(-500, 480) * 2
        v = math.ldexp(float(sq), e)
        u = bits_of(v)
        for d in (-2, -1, 0, 1, 2):
            I.add(u + d)
    # the squares of the halfway points: x just below and just above (y + u/2)^2
    for _ in range(size["sqrt_half"]):
        y = bits_of(math.ldexp(1.0 + rng.getrandbits(52) / 2.0 ** 52, rng.randint(-510, 510)))
        yf = frac_of(y)
        mid = yf + Fraction(2) ** (math.frexp(double_of(y))[1] - 54)
        sq = mid * mid
        lo = bits_of(float(Fraction(sq)))  # nearest double to the square
        for d in (-2, -1, 0, 1, 2):
            I.add(lo + d)
    # powers of 4 and 2 and their neighbours
    for k in range(-537, 512):
        v = math.ldexp(1.0, 2 * k)
        for d in (-3, -2, -1, 0, 1, 2, 3):
            I.add(bits_of(v) + d)
    for k in range(-1022, 1024):
        I.add(bits_of(math.ldexp(1.0, k)))
        I.add(bits_of(math.ldexp(1.0, k)) - 1)
    # uniform bit patterns, uniform values
    for _ in range(size["sqrt_bits"]):
        I.add(rng.getrandbits(63))
    for _ in range(size["sqrt_uniform"]):
        I.add(bits_of(rng.uniform(0.5, 4.0)))
        I.add(bits_of(rng.uniform(0.0, 1e6)))
    return I.items


def round_inputs(rng, size):
    I = Bits()
    for u in SPECIAL_BITS:
        I.add(u)
    for k in range(-12, 13):
        for f in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1, 8), Fraction(7, 8)):
            v = float(k + f)
            if k < 0 and f:
                v = float(k - f)
            for u in around_bits(bits_of(v), 2):
                I.add(u)
    for e in range(0, 2047):
        for m in (0, (1 << 52) - 1, 1 << 51):
            u = (e << 52) | m
            I.add(u)
            if 1000 <= e < 1100:
                I.add(u | (1 << 63))
    # halfway cases and neighbours, even and odd, up to 2^52
    for _ in range(size["round_half"]):
        n = rng.getrandbits(rng.randint(1, 51))
        v = n + 0.5
        for s in (1, -1):
            for d in (-1, 0, 1):
                I.add(bits_of(s * v) + d)
    for k in range(48, 56):
        for d in range(-4, 5):
            I.add(bits_of(2.0 ** k) + d)
            I.add(bits_of(-(2.0 ** k)) + d)
    for v in (0.5, 1.5, 2.5, 3.5, -0.5, -1.5, -2.5, -3.5, 4503599627370495.5, 4503599627370494.5, 4503599627370496.5):
        for d in (-2, -1, 0, 1, 2):
            I.add(bits_of(v) + d)
    for k in range(1, 53):
        I.add(rng.getrandbits(k) | (1 << (k - 1)))
        I.add((1 << 63) | rng.getrandbits(k) | (1 << (k - 1)))
    for _ in range(size["round_uniform"]):
        I.add(bits_of(rng.uniform(-10.0, 10.0)))
        I.add(bits_of(rng.uniform(-1.0, 1.0)))
        I.add(bits_of(rng.uniform(-1e6, 1e6)))
    for _ in range(size["round_bits"]):
        I.add(rnd_bits(rng, 1000, 1100))
        I.add(rnd_bits(rng))
    return I.items


def copysign_inputs(rng, size):
    I = Bits()
    for u in SPECIAL_BITS:
        for v in SPECIAL_BITS:
            I.add(u, v)
    for _ in range(size["copysign"]):
        I.add(rnd_bits(rng), rnd_bits(rng))
    return I.items


def scalbn_inputs(rng, size):
    I = Bits()
    ns = [0, 1, -1, 2, -2, 52, 53, 54, 55, -52, -53, -54, -55, 1022, 1023, 1024, 1025, -1021, -1022, -1023, -1024, -1025,
          -1073, -1074, -1075, -1076, 2046, 2047, 2048, 2098, -2098, 2099, -2099, 4999, 5000, 5001, -4999, -5000, -5001,
          INT_MAX, INT_MIN, INT_MAX - 1, INT_MIN + 1, 100000, -100000]
    xs = [0x3FF0000000000000, 0xBFF0000000000000, 0x3FFFFFFFFFFFFFFF, 0x0010000000000000, 0x000FFFFFFFFFFFFF,
          0x0000000000000001, 0x8000000000000001, 0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF, 0x4000000000000000, 0x3FE0000000000000,
          0x3FF8000000000000]
    for u in SPECIAL_BITS:
        for n in (0, 1, -1, 1000, -1000, INT_MAX, INT_MIN):
            I.add(u, n)
    for u in xs:
        for n in ns:
            I.add(u, n)
    # results at the subnormal edge: a significand with a tie below the last place that is kept
    for _ in range(size["scalbn_tie"]):
        s = rng.randint(1, 54)
        keep = rng.getrandbits(max(0, 52 - s)) if s < 53 else 0
        sig = (1 << 52) | (keep << s) if s < 53 else (1 << 52)
        if s <= 52:
            sig |= 1 << (s - 1)
        if rng.getrandbits(2) == 0:
            sig |= rng.getrandbits(max(0, s - 1))  # not quite a tie: sticky bits below
        ex = rng.randint(1, 2046)
        n = (1 - s) - ex
        sign = rng.getrandbits(1) << 63
        I.add(sign | (ex << 52) | (sig & ((1 << 52) - 1)), n)
    # a subnormal argument scaled up and a normal one scaled down to subnormal, by random amounts
    for _ in range(size["scalbn_rand"]):
        u = rnd_bits(rng, 0, 2046)
        e = (u >> 52) & 0x7FF
        kind = rng.getrandbits(2)
        if kind == 0:
            n = rng.randint(-2200, 2200)
        elif kind == 1:
            n = -e + rng.randint(-60, 5)        # lands near the bottom of the range
        elif kind == 2:
            n = 2046 - e + rng.randint(-5, 5)   # lands near the top
        else:
            n = rng.randint(-60, 60)
        I.add(u, n)
    return I.items


def frexp_inputs(rng, size):
    I = Bits()
    for u in SPECIAL_BITS:
        I.add(u)
    for e in range(0, 2047):
        for m in (0, (1 << 52) - 1, 1 << 51):
            I.add((e << 52) | m)
            if e % 16 == 0:
                I.add((1 << 63) | (e << 52) | m)
    for k in range(1, 53):
        I.add(1 << (k - 1))
        I.add((1 << 63) | (1 << (k - 1)))
        for _ in range(3):
            I.add(rng.getrandbits(k) | (1 << (k - 1)))
    for _ in range(size["frexp"]):
        I.add(rnd_bits(rng))
    return I.items


# ---------------------------------------------------------------------------

COMMITTED = dict(sqrt_per_exp=2, sqrt_sub=12, sqrt_exact=1200, sqrt_half=2500, sqrt_bits=2000, sqrt_uniform=800,
                 round_half=1000, round_uniform=800, round_bits=1000,
                 copysign=1500, scalbn_tie=2500, scalbn_rand=3000, frexp=1500)
FRESH = dict(sqrt_per_exp=1, sqrt_sub=8, sqrt_exact=300, sqrt_half=500, sqrt_bits=500, sqrt_uniform=250,
             round_half=200, round_uniform=200, round_bits=250,
             copysign=300, scalbn_tie=500, scalbn_rand=600, frexp=300)

ROUND_FNS = ("floor", "ceil", "trunc", "round", "rint")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--size", choices=("committed", "fresh"), default="committed")
    a = ap.parse_args()
    size = COMMITTED if a.size == "committed" else FRESH
    prov = "mpfr %s gmpy2 %s mpmath %s python %d.%d.%d" % (
        gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__, *sys.version_info[:3])
    os.makedirs(a.out, exist_ok=True)

    def rng_for(fn):
        return random.Random(a.seed * 1000003 + sum(map(ord, fn)))

    def write(fn, desc, lines):
        with open(os.path.join(a.out, fn + ".corpus"), "w") as f:
            f.write("# %s corpus for gmath_%s, from tools/oracle/gen_corpus_exact.py\n" % (fn, fn))
            f.write("# oracle: %s\n" % prov)
            f.write("# seed %d size %s entries %d\n" % (a.seed, a.size, len(lines)))
            f.write("# %s: the answer is exact, the test requires the result to equal it bit for bit\n" % desc)
            f.write("\n".join(lines) + "\n")
        sys.stderr.write("%s: %d entries\n" % (fn, len(lines)))

    h = lambda u: "%016x" % u
    lines = [h(u) + " " + h(sqrt_answer(u)) for (u,) in sqrt_inputs(rng_for("sqrt"), size)]
    write("sqrt", "x_bits r_bits", lines)
    ri = round_inputs(rng_for("round"), size)
    for fn in ROUND_FNS:
        write(fn, "x_bits r_bits", [h(u) + " " + h(round_answer(fn, u)) for (u,) in ri])
    write("fabs", "x_bits r_bits", [h(u) + " " + h(fabs_answer(u)) for (u,) in ri])
    write("copysign", "x_bits y_bits r_bits",
          [h(u) + " " + h(v) + " " + h(copysign_answer(u, v)) for (u, v) in copysign_inputs(rng_for("copysign"), size)])
    write("scalbn", "x_bits n(64, sign extended) r_bits",
          [h(u) + " " + int_hex(n) + " " + h(scalbn_answer(u, n)) for (u, n) in scalbn_inputs(rng_for("scalbn"), size)])
    fl = []
    for (u,) in frexp_inputs(rng_for("frexp"), size):
        r, e = frexp_answer(u)
        fl.append(h(u) + " " + h(r) + " " + int_hex(e))
    write("frexp", "x_bits fraction_bits e(64, sign extended)", fl)
    write("ilogb", "x_bits n(64, sign extended)",
          [h(u) + " " + int_hex(ilogb_answer(u)) for (u,) in frexp_inputs(rng_for("ilogb"), size)])


main()
