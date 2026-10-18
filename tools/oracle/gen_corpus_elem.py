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
"""Write the atan2, exp, log, pow and hypot corpus files for gmath_atan2,
gmath_exp, gmath_log, gmath_pow and gmath_hypot.

Runs in the pinned oracle image (tools/oracle/oracle.py corpus|fresh), after
gen_corpus.py.  Each line of <fn>.corpus is hexadecimal and fixed width:

    arg bits (16)   [arg2 bits (16)]   r_bits (16)   err_bits (8)

exp and log have one argument, atan2 (y, x), pow (x, y) and hypot (x, y) two.
r is the correctly rounded (to nearest, ties to even) double of the exact value
of fn, computed by MPFR (gmpy2) at 600 bits and rounded once, exactly, by
Python's correctly rounded int/int division; a value of 2^1024 - 2^970 or more
is r = +-infinity and one of 2^-1075 or less is r = +-0 (err 0 for both: the
test requires the result to be that infinity or that zero).  err is the IEEE
single whose value is (exact - r) / ulp(exact), the signed distance of the
exact value from r in units of the spacing of doubles at the exact value
(2^-1074 below 2^-1022).  A result y is within 1 ulp of the exact value iff
|((y - r) / ulp) - err| <= 1, which the test evaluates without needing the exact
value itself.  A NaN result is r = 7ff8000000000000 with err 0 (the test accepts
any NaN).

Every entry is also computed with mpmath, a separate implementation, and the
two must agree to 2^-400 relative; the run fails otherwise.  The special
values are in addition computed from the rules of C99 Annex F.9 written out
here (c99_special) and must agree with MPFR's answer.

The inputs, by function (see the functions below for the details):

  exp     specials; powers of two; the argument where the reduction's rounding
          is least certain (n ln2/128 and (n + 1/2) ln2/128); every one of the
          128 table rows; the overflow and the underflow thresholds and the
          boundary of the subnormals, a few doubles each side; arguments whose
          result is half way between two subnormals; uniform, small and
          log-uniform arguments
  log     specials; every power of two; every one of the 128 rows at both edges
          and inside; 1 +- k ulp and 1 +- 2^-k (where the cancellation bites);
          subnormals; uniform and log-uniform
  pow     the specials crossed with the specials; exact results (small integer
          powers, powers of two); negative bases with integer and non-integer
          exponents, odd and even, up to 2^53 and beyond; huge exponents with
          bases close to 1; exponents chosen so that the result is near the
          overflow, the underflow and the subnormal thresholds; typical,
          wide-range and half-integer exponents
  atan2   the specials crossed with the specials; all four quadrants; extreme
          ratios (past 2^1074); near an axis; near the diagonal; every table
          row and the half-way points where the nearest row changes; the
          thresholds of the direct path and of the scaling
  hypot   the specials crossed with the specials; Pythagorean triples scaled
          by powers of two and by small integers; both legs near DBL_MAX, near
          DBL_MIN and subnormal; the ratio thresholds; near equal legs; the
          doubles whose hypot is near the overflow threshold
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
NAN = math.nan
TWO1024M = Fraction(2) ** 1024 - Fraction(2) ** 970  # halfway between DBL_MAX and 2^1024
TWO_M1075 = Fraction(2) ** -1075
DBL_MAX = sys.float_info.max
DBL_MIN = sys.float_info.min
DENORM_MIN = 5e-324
QNAN = struct.unpack(">d", struct.pack(">Q", 0x7FF8000000000000))[0]


def bits_of(d):
    return struct.unpack(">Q", struct.pack(">d", d))[0]


def double_of(u):
    return struct.unpack(">d", struct.pack(">Q", u))[0]


def is_nan(d):
    return d != d


def exact_value(fn, args):
    """MPFR's value of fn(args) at 600 bits (plenty of exponent range)."""
    with gmpy2.context(precision=600, emin=EMIN, emax=EMAX):
        a = [gmpy2.mpfr(v) for v in args]
        if fn == "exp":
            return gmpy2.exp(a[0])
        if fn == "log":
            return gmpy2.log(a[0])
        if fn == "pow":
            return a[0] ** a[1]
        if fn == "atan2":
            return gmpy2.atan2(a[0], a[1])
        if fn == "hypot":
            return gmpy2.hypot(a[0], a[1])
    raise SystemExit("unknown function " + fn)


def mp_value(fn, args):
    mp.prec = 640
    a = [mp.mpf(v) for v in args]
    if fn == "exp":
        return mp.exp(a[0])
    if fn == "log":
        return mp.log(a[0])
    if fn == "pow":
        return mp.power(a[0], a[1])
    if fn == "atan2":
        return mp.atan2(a[0], a[1])
    if fn == "hypot":
        return mp.hypot(a[0], a[1])


def to_fraction(v):
    n, d = v.as_integer_ratio()
    return Fraction(int(n), int(d))


def ulp_exp(frac):
    a = abs(frac)
    k = a.numerator.bit_length() - a.denominator.bit_length()
    if a < Fraction(2) ** k:
        k -= 1
    return max(k, -1022) - 52


def is_odd_integer(y):
    return math.isfinite(y) and y == math.floor(y) and abs(y) < 2.0 ** 53 and int(y) % 2 == 1


def is_integer(y):
    return math.isfinite(y) and y == math.floor(y)


def c99_special(fn, args):
    """The result C99 Annex F.9 prescribes when an argument is special, as a
    double (a NaN is QNAN), or None when the arguments are not special."""
    if fn == "exp":
        x = args[0]
        if is_nan(x):
            return QNAN
        if x == INF:
            return INF
        if x == -INF:
            return 0.0
        if x == 0:
            return 1.0
        return None
    if fn == "log":
        x = args[0]
        if is_nan(x):
            return QNAN
        if x == 0:
            return -INF
        if x < 0:
            return QNAN
        if x == INF:
            return INF
        if x == 1:
            return 0.0
        return None
    if fn == "pow":
        x, y = args
        if y == 0:
            return 1.0
        if x == 1:
            return 1.0
        if is_nan(x) or is_nan(y):
            return QNAN
        if math.isinf(y):
            if x == -1:
                return 1.0
            if abs(x) < 1:
                return INF if y < 0 else 0.0
            return 0.0 if y < 0 else INF
        if x == 0:
            odd = is_odd_integer(y)
            neg = math.copysign(1.0, x) < 0
            if y < 0:
                return math.copysign(INF, -1.0 if (odd and neg) else 1.0)
            return math.copysign(0.0, -1.0 if (odd and neg) else 1.0)
        if math.isinf(x):
            odd = is_odd_integer(y)
            if x > 0:
                return INF if y > 0 else 0.0
            if y > 0:
                return -INF if odd else INF
            return -0.0 if odd else 0.0
        if x < 0 and not is_integer(y):
            return QNAN
        return None
    if fn == "atan2":
        y, x = args
        if is_nan(x) or is_nan(y):
            return QNAN
        sy = math.copysign(1.0, y)
        if y == 0:
            if math.copysign(1.0, x) < 0:
                return sy * math.pi
            return sy * 0.0
        if x == 0:
            return sy * math.pi / 2
        if math.isinf(y):
            if math.isinf(x):
                return sy * (3 * math.pi / 4 if x < 0 else math.pi / 4)
            return sy * math.pi / 2
        if math.isinf(x):
            return sy * math.pi if x < 0 else sy * 0.0
        return None
    if fn == "hypot":
        x, y = args
        if math.isinf(x) or math.isinf(y):
            return INF
        if is_nan(x) or is_nan(y):
            return QNAN
        return None
    raise SystemExit("unknown function " + fn)


def entry(fn, args):
    """The corpus line for fn(args), after checking MPFR against mpmath and,
    for the special values, against C99 Annex F."""
    key = " ".join("%016x" % bits_of(a) for a in args)
    spec = c99_special(fn, args)
    v = exact_value(fn, args)
    if spec is not None:
        # The Annex F value and MPFR's must agree (a NaN with a NaN; a value
        # given only to within rounding, like atan2's pi/4, to within 1 ulp).
        if is_nan(spec):
            if not v.is_nan():
                raise SystemExit("C99 says NaN for %s%r, MPFR says %s" % (fn, args, v))
            return "%s %016x %08x" % (key, bits_of(QNAN), 0), "nonfinite"
        if v.is_nan():
            raise SystemExit("C99 says %r for %s%r, MPFR says NaN" % (spec, fn, args))
        mf = float(v)
        if spec != mf and not (math.isfinite(spec) and math.isfinite(mf) and abs(spec - mf) <= math.ulp(spec)):
            raise SystemExit("C99 says %r for %s%r, MPFR says %r" % (spec, fn, args, mf))
        if math.copysign(1.0, spec) != math.copysign(1.0, mf) and spec == 0:
            raise SystemExit("the sign of the zero for %s%r: C99 %r MPFR %r" % (fn, args, spec, mf))
        if math.isinf(spec) or spec == 0:
            return "%s %016x %08x" % (key, bits_of(spec), 0), "special"
    if v.is_nan():
        raise SystemExit("MPFR gives NaN for %s%r and C99 did not say so" % (fn, args))
    if gmpy2.is_infinite(v):
        return "%s %016x %08x" % (key, bits_of(float(v)), 0), "inf"
    if v == 0:
        return "%s %016x %08x" % (key, bits_of(float(v)), 0), "zero"
    ex = to_fraction(v)
    if spec is None:
        w = mp_value(fn, args)
        wm = mp.mpf(w)
        n, d = v.as_integer_ratio()
        vm = mp.mpf(int(n)) / mp.mpf(int(d))
        if abs(wm - vm) > abs(vm) * mp.mpf(2) ** -400:
            raise SystemExit("MPFR and mpmath disagree on %s%r: %s vs %s" % (fn, args, v, wm))
    sign = 1 if ex > 0 else -1
    if abs(ex) >= TWO1024M:
        return "%s %016x %08x" % (key, bits_of(sign * INF), 0), "overflow"
    if abs(ex) <= TWO_M1075:
        return "%s %016x %08x" % (key, bits_of(math.copysign(0.0, sign)), 0), "underflow"
    try:
        r = ex.numerator / ex.denominator  # int / int is correctly rounded
    except OverflowError:
        return "%s %016x %08x" % (key, bits_of(sign * INF), 0), "overflow"
    rf = Fraction(r)
    err = (ex - rf) / Fraction(2) ** ulp_exp(ex)
    e32 = struct.unpack(">I", struct.pack(">f", err.numerator / err.denominator))[0]
    kind = "tie" if abs(err) > Fraction(49, 100) else "normal"
    if abs(r) < DBL_MIN:
        kind = "subnormal"
    return "%s %016x %08x" % (key, bits_of(r), e32), kind


def finite(d):
    return math.isfinite(d)


class Inputs:
    """An ordered, duplicate-free list of argument tuples."""

    def __init__(self, arity):
        self.arity = arity
        self.seen = set()
        self.items = []

    def add(self, *args):
        assert len(args) == self.arity
        k = tuple(bits_of(a) for a in args)
        if k not in self.seen:
            self.seen.add(k)
            self.items.append(tuple(args))


def lu(rng, lo, hi, signed=False):
    """A log-uniform magnitude in [lo, hi), a random sign when signed."""
    v = 2.0 ** rng.uniform(math.log2(lo), math.log2(hi))
    if v >= hi:
        v = math.nextafter(hi, 0)
    return -v if signed and rng.getrandbits(1) else v


def uni(rng, a, b):
    return a + (b - a) * (rng.getrandbits(53) / (1 << 53))


def around(d, n):
    """d and the n doubles each side of it."""
    out = [d]
    lo = hi = d
    for _ in range(n):
        lo = math.nextafter(lo, -INF)
        hi = math.nextafter(hi, INF)
        out += [lo, hi]
    return out


def mpf_to_double_floor(v, direction):
    """The double nearest to the mpmath value v, then moved to be on the
    `direction` side of v (-1 below, +1 above)."""
    d = float(v)
    if direction < 0 and mp.mpf(d) > v:
        d = math.nextafter(d, -INF)
    if direction > 0 and mp.mpf(d) < v:
        d = math.nextafter(d, INF)
    return d


# ---------------------------------------------------------------------------
# Witnesses found by search (story 4, scratch search; the corpus does not
# depend on the library, only on these bit patterns).  Each is an input at
# which a one-ulp change of the named coefficient (or, for the arctangent's
# rows, of G1 or G2 of the named row) changes the result: such a change moves
# the value by 2^-62 to 2^-75 of the result, so a random input shows it with
# probability between 2^-9 and 2^-22; the search drew inputs from the
# distribution where the coefficient has most weight (the function's reduced
# argument at its largest) until it had two, one for the rows, and they were
# found against the committed library (4e6 to 1e8 inputs per change).
# tools/check-planted-elem.py plants each change and shows the committed hash
# catches it.  Coefficients with no witness in 1e8 inputs are listed there as
# not visible.
# ---------------------------------------------------------------------------
WITNESSES = {
    "exp": (
        0xc0842243ef5f9f51,  # exp c0 up one ulp
        0xc07335d1aff0b78d,  # exp c0 up one ulp
        0x403576c9227d1d60,  # exp c0 down one ulp
        0x40414e5446cfcc50,  # exp c0 down one ulp
    ),
    "log": (
        0x3fefbe7aa0b5df9b,  # log P0 up one ulp
        0x3ff01c5912c14cb3,  # log P0 up one ulp
        0x3ff011d1953ef081,  # log P0 down one ulp
        0x3ff01d13b0fc10a1,  # log P0 down one ulp
        0x3feff01686bac7bc,  # log P1 up one ulp
        0x3ff0071746493869,  # log P1 up one ulp
        0x3fefe3a5f96d8a93,  # log P1 down one ulp
        0x3ff01c87366623f3,  # log P1 down one ulp
        0x3ff01d1a494a2e9b,  # log P2 up one ulp
        0x3fefe37fc0283aca,  # log P2 up one ulp
        0x3ff01b60b23d2eb5,  # log P2 down one ulp
        0x3ff01ebdee54297a,  # log P2 down one ulp
    ),
    "pow": (
        (0x3fefe3922cfb12b6, 0x4105f57c8ad85df8),  # pow R0 up one ulp
        (0x3ff012bf0ef98a91, 0xc0f49286e50666c0),  # pow R0 up one ulp
        (0x3ff01fb4523a2a0b, 0xc0f223700ceebde5),  # pow R2 up one ulp
        (0x3ff01d8c5ccb2eeb, 0xc0f390f5160bfdd4),  # pow R2 up one ulp
        (0x3fefeccffa5388c6, 0x4108c2af7fd82203),  # pow R0 down one ulp
        (0x3fefec5b27d395fd, 0xc10bb7f4ba80b10e),  # pow R0 down one ulp
        (0x3fefdebd758dcb12, 0xc0fa903186b7a9aa),  # pow R1 down one ulp
    ),
    "atan2": (
        (0x3fc60f2d9768aaf3, 0x3ff724614cdd2819),  # atan2 P0 up one ulp
        (0x3fc9b0b501e27de3, 0x3ffbd204598a0b1b),  # atan2 P0 up one ulp
        (0x3fc7723987fbeb87, 0x3ff85273b87a21ae),  # atan2 P0 down one ulp
        (0x3fb0ab20774af7bd, 0x3fe5d5cd9717ae2d),  # atan2 P0 down one ulp
        (0x3fbd5d8705833896, 0x3ff48b013a544f66),  # atan2 P1 up one ulp
        (0x3faadddddc7023bc, 0x3fe254fc17395c76),  # atan2 P1 up one ulp
        (0x3facb96753ecf4ef, 0x3fe0ad2cc8081ecb),  # atan2 P1 down one ulp
        (0x3fb04947ee8a6cd3, 0x3fe15fd3463dd7a5),  # atan2 P1 down one ulp
        (0x3fb2b41703f054a6, 0x3fe448e1ea1f711b),  # atan2 P2 up one ulp
        (0x3fc4bcdc5119826b, 0x3ff599ce79424d72),  # atan2 P2 down one ulp
        (0x3fb8706c93f9496d, 0x3fe78ffe5844b94e),  # atan2 row 8 G1 up one ulp
        (0x3fb5c4b7d746711d, 0x3fe492c9a1bbc18f),  # atan2 row 8 G1 down one ulp
        (0x3fbb26978abfd530, 0x3fea7469e8d8bdea),  # atan2 row 8 G2 up one ulp
        (0x3fb1b51c6e3fc2a4, 0x3fe0bc3022e6e65a),  # atan2 row 8 G2 down one ulp
        (0x3fcb8967a0cca5e8, 0x3ff86297a50a5e16),  # atan2 row 9 G1 up one ulp
        (0x3fb5387a7a7698e9, 0x3fe39a60ca5ee53d),  # atan2 row 9 G1 down one ulp
        (0x3fcd5accfcb26bac, 0x3ffab69f026dde1e),  # atan2 row 9 G2 up one ulp
        (0x3fc915b244ba2f57, 0x3ff71aad6985f1dd),  # atan2 row 9 G2 down one ulp
        (0x3fb5c0cf270b50a8, 0x3fe1e75873bb6034),  # atan2 row 10 G1 up one ulp
        (0x3fc3f3c4c3930529, 0x3ff089039a2aee64),  # atan2 row 10 G1 down one ulp
        (0x3fc4ca791fbe5793, 0x3ff01480d93da830),  # atan2 row 10 G2 up one ulp
        (0x3fb4cc0d1f8a577f, 0x3fe181879be8c206),  # atan2 row 10 G2 down one ulp
        (0x3fbbbe7adb038269, 0x3fe3c0119e41c60a),  # atan2 row 11 G1 up one ulp
        (0x3fd1671ab20fc644, 0x3ffa4c99bfa8d891),  # atan2 row 11 G1 down one ulp
        (0x3fbdffc7f1038898, 0x3fe4fc2cbaf3162a),  # atan2 row 11 G2 up one ulp
        (0x3fd3c460706938b3, 0x3ffdf976421034b7),  # atan2 row 11 G2 down one ulp
        (0x3fba6bec8f36d57c, 0x3fe1eb78710fd1a9),  # atan2 row 12 G1 up one ulp
        (0x3fc58cca8bc17046, 0x3fedbe824d42f38d),  # atan2 row 12 G1 down one ulp
        (0x3fd88c37a7868c41, 0x3fff9b5de2da2491),  # atan2 row 12 G2 up one ulp
        (0x3fc8fbf3ad24f081, 0x3feffb2c20ba406f),  # atan2 row 12 G2 down one ulp
        (0x3fc66a9af5475c4c, 0x3fec59ee8bb4c79b),  # atan2 row 13 G1 up one ulp
        (0x3fbb9e687b57bdfb, 0x3fe0619fd71d03d9),  # atan2 row 13 G1 down one ulp
        (0x3fc14b0c9083a727, 0x3fe4c9cf56114ec9),  # atan2 row 13 G2 up one ulp
        (0x3fca9488fcb0318c, 0x3ff0fe5d26d28496),  # atan2 row 13 G2 down one ulp
        (0x3fbe3d7d876358ac, 0x3fe1a8f22aff4c4c),  # atan2 row 14 G1 up one ulp
        (0x3fd3211fc83536e8, 0x3ff6803a213a4982),  # atan2 row 14 G1 down one ulp
        (0x3fd7ba40fca66797, 0x3ffbe5980f476fe3),  # atan2 row 14 G2 up one ulp
        (0x3fc77dee2de476f3, 0x3feb66d7fddd9a59),  # atan2 row 14 G2 down one ulp
        (0x3fbfb6d0711efef1, 0x3fe0619fd71d03d9),  # atan2 row 15 G1 up one ulp
        (0x3fd92752cd53b138, 0x3ffb3fd6d040d030),  # atan2 row 15 G1 down one ulp
        (0x3fd10bb161103738, 0x3ff1d7806dd38c5c),  # atan2 row 15 G2 up one ulp
        (0x3fd3cf47c4cea943, 0x3ff5b297295b3b44),  # atan2 row 15 G2 down one ulp
        (0x3fd20a7c0f88c091, 0x3ff24bab0dd2faeb),  # atan2 row 16 G1 up one ulp
        (0x3fd38ec69f49cde8, 0x3ff421e6fdc139a1),  # atan2 row 16 G1 down one ulp
        (0x3fd46d19c68d5fcd, 0x3ff4c90b5f612e0a),  # atan2 row 16 G2 up one ulp
        (0x3fc2f3010b1849de, 0x3fe3462e1381b2b5),  # atan2 row 16 G2 down one ulp
        (0x3fcbf6195d81cd2a, 0x3fe9e7bee08bcaec),  # atan2 row 17 G1 up one ulp
        (0x3fcf9f22261aa0e4, 0x3fee7154ff900539),  # atan2 row 17 G1 down one ulp
        (0x3fc4ed2dc5f210db, 0x3fe3f13ec363e68d),  # atan2 row 17 G2 up one ulp
        (0x3fde872fde8668c8, 0x3ffd963622913ad0),  # atan2 row 17 G2 down one ulp
        (0x3fd0f21e7612d1b6, 0x3feef05a2dc94b12),  # atan2 row 18 G1 up one ulp
        (0x3fd03f056f6cf574, 0x3fec571c9cae164d),  # atan2 row 18 G1 down one ulp
        (0x3fe145df97bfdce6, 0x3fff447c5846f3c7),  # atan2 row 18 G2 up one ulp
        (0x3fd02bee1be2c32e, 0x3fec4aa3801e0ccd),  # atan2 row 18 G2 down one ulp
        (0x3fc97f33937a8859, 0x3fe5fde6e2b5724d),  # atan2 row 19 G1 up one ulp
        (0x3fd6bc55bd3ed52f, 0x3ff379b18f23c206),  # atan2 row 19 G1 down one ulp
        (0x3fd3f75f8fafa34b, 0x3ff06cf32653f85d),  # atan2 row 19 G2 up one ulp
        (0x3fcce83db3616ddb, 0x3fe7e87d68723aec),  # atan2 row 19 G2 down one ulp
        (0x3fda4df577e2a674, 0x3ff59001260db541),  # atan2 row 20 G1 up one ulp
        (0x3fd1083c3afa299d, 0x3febdb67bea99118),  # atan2 row 20 G1 down one ulp
        (0x3fd04f7dc88f72f5, 0x3fea88586a22537e),  # atan2 row 20 G2 up one ulp
        (0x3fd53f5a5119e60a, 0x3ff1544183caf109),  # atan2 row 20 G2 down one ulp
        (0x3fc551edb70f2cb6, 0x3fe050a30e07c1ec),  # atan2 row 21 G1 up one ulp
        (0x3fd14f540951a295, 0x3fead235d176f0d7),  # atan2 row 21 G1 down one ulp
        (0x3fd58c8650207c80, 0x3ff0bd1a57ea1218),  # atan2 row 21 G2 up one ulp
        (0x3fe0257032a396f1, 0x3ff8303ba80a5278),  # atan2 row 21 G2 down one ulp
        (0x3fca89abe1a866b6, 0x3fe39a60ca5ee53d),  # atan2 row 22 G1 up one ulp
        (0x3fdd5b1c2b377829, 0x3ff4e64a6f5a2b7e),  # atan2 row 22 G1 down one ulp
        (0x3fd93ea6596d5fdd, 0x3ff2c8f1c0db80fd),  # atan2 row 22 G2 up one ulp
        (0x3fddabf5b5f29638, 0x3ff51dec2d968ff6),  # atan2 row 22 G2 down one ulp
        (0x3fe2e9a94766c3b6, 0x3ffa131dfcf16086),  # atan2 row 23 G1 up one ulp
        (0x3fdacd1e20a3a5d7, 0x3ff2550595e69cf9),  # atan2 row 23 G1 down one ulp
        (0x3fd5bce255107814, 0x3fede4dd5f70a0a9),  # atan2 row 23 G2 up one ulp
        (0x3fe35c5b53442939, 0x3ffb808b493e9da8),  # atan2 row 23 G2 down one ulp
        (0x3fd3f2b347436db0, 0x3feafa4984c54808),  # atan2 row 24 G1 up one ulp
        (0x3fd521dbdbff7d60, 0x3feb99f763baf009),  # atan2 row 24 G1 down one ulp
        (0x3fd4c95e59decb6f, 0x3fec49bb6af521d0),  # atan2 row 24 G2 up one ulp
        (0x3fe1b53ae6e3d73a, 0x3ff73227ce08ba91),  # atan2 row 24 G2 down one ulp
        (0x3fca186c1f01a1e1, 0x3fe0619fd71d03d9),  # atan2 row 25 G1 up one ulp
        (0x3fe353483caf0b69, 0x3ff853db294b6f02),  # atan2 row 25 G1 down one ulp
        (0x3fd615db168ae6d9, 0x3feccf822a952709),  # atan2 row 25 G2 up one ulp
        (0x3fe3acb1357ab625, 0x3ff99b8f91e25da2),  # atan2 row 25 G2 down one ulp
        (0x3fe22947e31b9c5b, 0x3ff60ed2be5fb022),  # atan2 row 26 G1 up one ulp
        (0x3fd18f244b54f52d, 0x3fe5fde6e2b5724d),  # atan2 row 26 G1 down one ulp
        (0x3fdfa44ab0534f3c, 0x3ff32b7a499700e8),  # atan2 row 26 G2 up one ulp
        (0x3fe8e4e880135fe2, 0x3ffe5bbb0e521e05),  # atan2 row 26 G2 down one ulp
        (0x3fce02b7319a3f4c, 0x3fe1eb78710fd1a9),  # atan2 row 27 G1 up one ulp
        (0x3fe6c2cd9b3324f4, 0x3ffb0380564ed5bc),  # atan2 row 27 G1 down one ulp
        (0x3feae55b2096f315, 0x3fff557bdefaeb47),  # atan2 row 27 G2 up one ulp
        (0x3fd577777270d008, 0x3fe904dead598ec0),  # atan2 row 27 G2 down one ulp
        (0x3fd22bcc576ca1e7, 0x3fe47a0460b0c574),  # atan2 row 28 G1 up one ulp
        (0x3fe182acbba28848, 0x3ff42fbd39da857e),  # atan2 row 28 G1 down one ulp
        (0x3fd16143c3968a55, 0x3fe42b1d01b3c59b),  # atan2 row 28 G2 up one ulp
        (0x3fd3330932b87db9, 0x3fe64a1bb92475c4),  # atan2 row 28 G2 down one ulp
        (0x3fe03f562b3f95b5, 0x3ff231df2745a546),  # atan2 row 29 G1 up one ulp
        (0x3fd971ea8394b2e2, 0x3feb99f763baf009),  # atan2 row 29 G1 down one ulp
        (0x3fe17c4e977c6219, 0x3ff31e8f6e1747fc),  # atan2 row 29 G2 up one ulp
        (0x3fdafc723a0712bc, 0x3fed5c1bc49bcd36),  # atan2 row 29 G2 down one ulp
        (0x3fec77a6a4ff8630, 0x3ffde0fa085c0853),  # atan2 row 30 G1 up one ulp
        (0x3fd396189502b15a, 0x3fe492c9a1bbc18f),  # atan2 row 30 G1 down one ulp
        (0x3fe2f1773c5d54d2, 0x3ff46fd8b606d133),  # atan2 row 30 G2 up one ulp
        (0x3fe8ce88292367cd, 0x3ffacbdd7c9d2aa3),  # atan2 row 30 G2 down one ulp
        (0x3fea4fc25d4c374b, 0x3ffb1326003eddb1),  # atan2 row 31 G1 up one ulp
        (0x3fe0b59e0f82e3bf, 0x3ff109d08ef02415),  # atan2 row 31 G1 down one ulp
        (0x3fe7f4ae05ecbeeb, 0x3ff90a12312cbc07),  # atan2 row 31 G2 up one ulp
        (0x3fd5f781766ac2d3, 0x3fe6f9d42cb4d0dc),  # atan2 row 31 G2 down one ulp
        (0x3fe2f59c7b4f5e72, 0x3ff31d61a8cdf1cb),  # atan2 row 32 G1 up one ulp
        (0x3fd20f9a9796d6be, 0x3fe23b1d9099b0e5),  # atan2 row 32 G1 down one ulp
        (0x3fe6184543c5b559, 0x3ff5d0abf6a9ef5b),  # atan2 row 32 G2 up one ulp
        (0x3feb77af6375d008, 0x3ffb140843ba774d),  # atan2 row 32 G2 down one ulp
        (0x3fdc2433ab51c059, 0x3feb0aada57c6ff5),  # atan2 row 33 G1 up one ulp
        (0x3fdb892ed0d6add1, 0x3feaf7202fcc6fc8),  # atan2 row 33 G1 down one ulp
        (0x3fdb0d06871bc642, 0x3fea87d3ccd18b2d),  # atan2 row 33 G2 up one ulp
        (0x3fe80eb2c59fe6ec, 0x3ff7220300213a47),  # atan2 row 33 G2 down one ulp
        (0x3fe5180d0d432659, 0x3ff3b84715768835),  # atan2 row 34 G1 up one ulp
        (0x3fe7a0b438df0965, 0x3ff6803a213a4982),  # atan2 row 34 G1 down one ulp
        (0x3fe3702aaab98fb2, 0x3ff2102650432a5c),  # atan2 row 34 G2 up one ulp
        (0x3fe448ceb60825ba, 0x3ff2d5af6d2b3310),  # atan2 row 34 G2 down one ulp
        (0x3fd6a67d4c934d18, 0x3fe47a0460b0c574),  # atan2 row 35 G1 up one ulp
        (0x3fd9670a690b5813, 0x3fe75a3c8e92b18e),  # atan2 row 35 G1 down one ulp
        (0x3fd5a15f849042ca, 0x3fe3b31ae205d9a8),  # atan2 row 35 G2 up one ulp
        (0x3ff040699e9da187, 0x3ffd51bccf65da04),  # atan2 row 35 G2 down one ulp
        (0x3fda21dc4d7fed9f, 0x3fe75a3c8e92b18e),  # atan2 row 36 G1 up one ulp
        (0x3fd24b09a2f96fe5, 0x3fe077f37a801ef9),  # atan2 row 36 G1 down one ulp
        (0x3fdd659f5b4d7e62, 0x3fe9e3ce38802f6a),  # atan2 row 36 G2 up one ulp
        (0x3fd8dc1cb16663cb, 0x3fe6661c63cc7dec),  # atan2 row 36 G2 down one ulp
        (0x3fed6f5eb553edfa, 0x3ff94c02f5f7430b),  # atan2 row 37 G1 up one ulp
        (0x3fe87980f9ce0077, 0x3ff4e64a6f5a2b7e),  # atan2 row 37 G1 down one ulp
        (0x3fe064b3777f854c, 0x3febfd318e533c04),  # atan2 row 37 G2 up one ulp
        (0x3fd29bca7809b2d0, 0x3fe04a4e5a39e21a),  # atan2 row 37 G2 down one ulp
        (0x3fe0fabba8ace1b2, 0x3fec571c9cae164d),  # atan2 row 38 G1 up one ulp
        (0x3fe4689f14712c42, 0x3ff1196a718b8e2f),  # atan2 row 38 G1 down one ulp
        (0x3fd474bb2538d5aa, 0x3fe10606b42954a2),  # atan2 row 38 G2 up one ulp
        (0x3fe70650f2ec17cb, 0x3ff39e6c7e889db3),  # atan2 row 38 G2 down one ulp
        (0x3fe04d63b07005fc, 0x3feb0c1c5f4bdd9a),  # atan2 row 39 G1 up one ulp
        (0x3fe83fc15607c860, 0x3ff421e6fdc139a1),  # atan2 row 39 G1 down one ulp
        (0x3fe68ddcb725f128, 0x3ff252ff7fb87bc1),  # atan2 row 39 G2 up one ulp
        (0x3fd60c120060cb0d, 0x3fe1f488c0c4978a),  # atan2 row 39 G2 down one ulp
        (0x3fda03f7978d5dd6, 0x3fe492c9a1bbc18f),  # atan2 row 40 G1 up one ulp
        (0x3febc946bfdf6f26, 0x3ff65e803ba30dbe),  # atan2 row 40 G1 down one ulp
        (0x3fd762d30603741a, 0x3fe28d6c6a00794f),  # atan2 row 40 G2 up one ulp
        (0x3fe2a3e556f8d47c, 0x3fee0a9626af697d),  # atan2 row 40 G2 down one ulp
        (0x3fd7b05b93d6bfa2, 0x3fe2708797924344),  # atan2 row 41 G1 up one ulp
        (0x3fee19adaa827736, 0x3ff7b63c28b192aa),  # atan2 row 41 G1 down one ulp
        (0x3ff320d1d2e02c8c, 0x3ffe35209b3a1776),  # atan2 row 41 G2 up one ulp
        (0x3fe739e8725b06a6, 0x3ff2469d40fb0233),  # atan2 row 41 G2 down one ulp
        (0x3fd779f8023c454a, 0x3fe1f7fdc9a7e600),  # atan2 row 42 G1 up one ulp
        (0x3feee280db8da3a3, 0x3ff7cea67c16e366),  # atan2 row 42 G1 down one ulp
        (0x3fd57a51e6a9180b, 0x3fe089dc3bae40a9),  # atan2 row 42 G2 up one ulp
        (0x3fe4d4c28be1a0d0, 0x3ff00be797f8c810),  # atan2 row 42 G2 down one ulp
        (0x3fe164f4bbe8644b, 0x3fea2e4497607f8d),  # atan2 row 43 G1 up one ulp
        (0x3fd8febef9a645f8, 0x3fe273908fd89776),  # atan2 row 43 G1 down one ulp
        (0x3ff3ef4154c80671, 0x3ffe019a8bb93315),  # atan2 row 43 G2 up one ulp
        (0x3fe12db8f23ff66e, 0x3fe9d502ed42f4f0),  # atan2 row 43 G2 down one ulp
        (0x3fe2c9b2ddda171c, 0x3feb8e1976e3bb06),  # atan2 row 44 G1 up one ulp
        (0x3fdf99d8cbbdb14d, 0x3fe6cb12cbf54587),  # atan2 row 44 G1 down one ulp
        (0x3ff0f6e34a81e02a, 0x3ff8d60d9d2150dd),  # atan2 row 44 G2 up one ulp
        (0x3fe5c79639cf77ff, 0x3fefff1353046896),  # atan2 row 44 G2 down one ulp
        (0x3fd6b0a9e41c9096, 0x3fe00bf1da78bda1),  # atan2 row 45 G1 up one ulp
        (0x3fedff7ba1ac08d4, 0x3ff59001260db541),  # atan2 row 45 G1 down one ulp
        (0x3fd9feb458015dbf, 0x3fe26cfcf2a884d2),  # atan2 row 45 G2 up one ulp
        (0x3fe89704ab3e2e27, 0x3ff18f8914366ed8),  # atan2 row 45 G2 down one ulp
        (0x3ff01057e3953a11, 0x3ff68070870ac247),  # atan2 row 46 G1 up one ulp
        (0x3ff2fac20f54773f, 0x3ffa52b90074ca54),  # atan2 row 46 G1 down one ulp
        (0x3fdde627c1c26309, 0x3fe49ec6bb6d3cff),  # atan2 row 46 G2 up one ulp
        (0x3fd9f4e1393f5158, 0x3fe2381ca04800f8),  # atan2 row 46 G2 down one ulp
        (0x3fe42538130f041e, 0x3febaf3d682c7e7f),  # atan2 row 47 G1 up one ulp
        (0x3fe267e31c941ee9, 0x3fe8dcd1fbf1aadd),  # atan2 row 47 G1 down one ulp
        (0x3febbc00c9f6f95b, 0x3ff311057cadb8f8),  # atan2 row 47 G2 up one ulp
        (0x3ff2289adb576ad4, 0x3ff877c95347f0b5),  # atan2 row 47 G2 down one ulp
        (0x3fe93284cf87f77a, 0x3ff0efbe169199f8),  # atan2 row 48 G1 up one ulp
        (0x3fdf368b21fe3128, 0x3fe501b53b021e18),  # atan2 row 48 G1 down one ulp
        (0x3ff04090eb9c6a42, 0x3ff58483e0f1bb93),  # atan2 row 48 G2 up one ulp
        (0x3ff084df2a3ad75e, 0x3ff63f4cfb669fe8),  # atan2 row 48 G2 down one ulp
        (0x3fe194c9ddce0215, 0x3fe6cb12cbf54587),  # atan2 row 49 G1 up one ulp
        (0x3fdc45fa740be5a6, 0x3fe2958b0ab82ac1),  # atan2 row 49 G1 down one ulp
        (0x3fe681f1cce8aa97, 0x3fed241379012fb2),  # atan2 row 49 G2 up one ulp
        (0x3fe3a01dc2e628f3, 0x3fe9c03f23be7221),  # atan2 row 49 G2 down one ulp
        (0x3ff51ea0d2ff708b, 0x3ffb49e6a1099806),  # atan2 row 50 G1 up one ulp
        (0x3fe209ab85b0eb1e, 0x3fe74a42893306a3),  # atan2 row 50 G1 down one ulp
        (0x3fdde80a804f642f, 0x3fe33e3a3ad546e6),  # atan2 row 50 G2 up one ulp
        (0x3ff21a9cd6952af0, 0x3ff70bbf278365f3),  # atan2 row 50 G2 down one ulp
        (0x3fee8a7b99928879, 0x3ff308fab00bcf75),  # atan2 row 51 G1 up one ulp
        (0x3ff8ce3f01fa3b9e, 0x3fff4667e0389136),  # atan2 row 51 G1 down one ulp
        (0x3ff78df25c96504a, 0x3ffdd10518704cfe),  # atan2 row 51 G2 up one ulp
        (0x3ff89f285c085291, 0x3fff3007cccd5218),  # atan2 row 51 G2 down one ulp
        (0x3fe8898c3f6b560d, 0x3fee76d6dbadc235),  # atan2 row 52 G1 up one ulp
        (0x3ff2aaebd9492bcd, 0x3ff72e045acd9572),  # atan2 row 52 G1 down one ulp
        (0x3fe7ce9c622a8fe0, 0x3fed77eb64904a92),  # atan2 row 52 G2 up one ulp
        (0x3ff603dc6a8948a8, 0x3ffb4690bfdc644a),  # atan2 row 52 G2 down one ulp
        (0x3fe907885947ab29, 0x3fee7154ff900539),  # atan2 row 53 G1 up one ulp
        (0x3fdc679d23c531ee, 0x3fe10af2d7d90cbb),  # atan2 row 53 G1 down one ulp
        (0x3ff3137afa3d0138, 0x3ff73fd649d0d24a),  # atan2 row 53 G2 up one ulp
        (0x3fe073351876a110, 0x3fe3f9e199db90d1),  # atan2 row 53 G2 down one ulp
        (0x3fec5f7873c34459, 0x3ff0efbe169199f8),  # atan2 row 54 G1 up one ulp
        (0x3ff8964b674956d1, 0x3ffd403a30e9047d),  # atan2 row 54 G1 down one ulp
        (0x3fe3152af7201233, 0x3fe6c1832b381403),  # atan2 row 54 G2 up one ulp
        (0x3fe355bddd39ea1c, 0x3fe71176c4f094e9),  # atan2 row 54 G2 down one ulp
        (0x3fe490fb5aa15cef, 0x3fe7c8e9714e0b15),  # atan2 row 55 G1 up one ulp
        (0x3fe37ab8fb8734a0, 0x3fe6cf20e55ae26b),  # atan2 row 55 G1 down one ulp
        (0x3fe898e04bca8543, 0x3fec790c7092a8cf),  # atan2 row 55 G2 up one ulp
        (0x3fe15e859c9055bd, 0x3fe4101bf6f32d54),  # atan2 row 55 G2 down one ulp
        (0x3ff2b4b20b66516c, 0x3ff53ef652060423),  # atan2 row 56 G1 up one ulp
        (0x3fef65fba6fd21ac, 0x3ff2196221f45d78),  # atan2 row 56 G1 down one ulp
        (0x3fe6371c8406c733, 0x3fe99459666b7f50),  # atan2 row 56 G2 up one ulp
        (0x3fe1f478459d8062, 0x3fe4b179c303306a),  # atan2 row 56 G2 down one ulp
        (0x3ff29eee54be559a, 0x3ff4ed915f596f8c),  # atan2 row 57 G1 up one ulp
        (0x3fdf721aa869a1c8, 0x3fe1858c86abc3d1),  # atan2 row 57 G1 down one ulp
        (0x3fe34af98d0be9e1, 0x3fe5d4f77456730e),  # atan2 row 57 G2 up one ulp
        (0x3ffc3499fd98969d, 0x3fffe8c76cca5aa1),  # atan2 row 57 G2 down one ulp
        (0x3fef0bc722b9ef30, 0x3ff0fe3e68a956f3),  # atan2 row 58 G1 up one ulp
        (0x3ff37695ceb22905, 0x3ff595f59c17f3c1),  # atan2 row 58 G1 down one ulp
        (0x3ff5b614dc77d420, 0x3ff7e5ba4cd41104),  # atan2 row 58 G2 up one ulp
        (0x3fe63e20c82cd939, 0x3fe8bc8f4ec2542d),  # atan2 row 58 G2 down one ulp
        (0x3ff753598fa14312, 0x3ff9769de24bfa1f),  # atan2 row 59 G1 up one ulp
        (0x3fe9a9213889f9f5, 0x3feb99f763baf009),  # atan2 row 59 G1 down one ulp
        (0x3fe601a302a3df4f, 0x3fe80cd57e57068d),  # atan2 row 59 G2 up one ulp
        (0x3fe955a7b7d437ed, 0x3feb41c5d26ca570),  # atan2 row 59 G2 down one ulp
        (0x3fe774bdc3c1359e, 0x3fe8dcd1fbf1aadd),  # atan2 row 60 G1 up one ulp
        (0x3ff7e54c9c6fcf2d, 0x3ff9480bdf953bb9),  # atan2 row 60 G1 down one ulp
        (0x3ffda0ea2a80665b, 0x3fff66789966ff51),  # atan2 row 60 G2 up one ulp
        (0x3ff166b281f7fadb, 0x3ff29f8869162060),  # atan2 row 60 G2 down one ulp
        (0x3ffe008ed7babbfc, 0x3fff3bcc393ef6d5),  # atan2 row 61 G1 up one ulp
        (0x3ff1898f1dfb0984, 0x3ff2842c5d2c36bb),  # atan2 row 61 G1 down one ulp
        (0x3fe2eddbaa3fd60d, 0x3fe3b5b304e5a0fd),  # atan2 row 61 G2 up one ulp
        (0x3ffd7162d9394042, 0x3ffea8246f80d28b),  # atan2 row 61 G2 down one ulp
        (0x3fdeef0ffdfb6445, 0x3fe01781d0dae4c1),  # atan2 row 62 G1 up one ulp
        (0x3ff98f704f71a9d4, 0x3ffa52b90074ca54),  # atan2 row 62 G1 down one ulp
        (0x3ff76b1564ac1bd7, 0x3ff85d7294449445),  # atan2 row 62 G2 up one ulp
        (0x3fe9110f64306fb3, 0x3fe9b26c731d9618),  # atan2 row 62 G2 down one ulp
        (0x3ffaf72d7a65dde9, 0x3ffb797dac0bf5e3),  # atan2 row 63 G1 up one ulp
        (0x3fea4adfc0b57f33, 0x3fea9ca1ca63d391),  # atan2 row 63 G1 down one ulp
        (0x3fefa32e86179a3a, 0x3feff0e854dea4f4),  # atan2 row 63 G2 up one ulp
        (0x3ffdaba910850549, 0x3ffe525beb734cd4),  # atan2 row 63 G2 down one ulp
        (0x3ff059e7ecce66c0, 0x3ff0793508d8f29b),  # atan2 row 64 G1 up one ulp
        (0x3ff20a2c4450179a, 0x3ff2289f347eeae9),  # atan2 row 64 G1 down one ulp
        (0x3ffb8029243b3dbf, 0x3ffb9d91c2a17e0d),  # atan2 row 64 G2 up one ulp
        (0x3fe056af9abeb754, 0x3fe072625212601a),  # atan2 row 64 G2 down one ulp
    ),
    "hypot": (
    ),
}

SPECIAL_DOUBLES = (0.0, -0.0, 1.0, -1.0, INF, -INF, QNAN, double_of(0xFFF8000000000000),
                   double_of(0x7FF0000000000001), DENORM_MIN, -DENORM_MIN, DBL_MIN, -DBL_MIN, DBL_MAX, -DBL_MAX,
                   2.0, -2.0, 0.5, -0.5, 3.0, -3.0, 1e-300, -1e-300, 1e300, -1e300, 2.0 ** 53, -(2.0 ** 53),
                   2.0 ** 53 + 2.0, 2.0 ** 52 + 1.0, -(2.0 ** 52 + 1.0), 1.5, -1.5, 0.25, 10.0, 1e308,
                   math.nextafter(1.0, 2.0), math.nextafter(1.0, 0.0), -math.nextafter(1.0, 0.0))


def exp_inputs(rng, size):
    I = Inputs(1)
    add = I.add
    for d in (0.0, -0.0, INF, -INF, QNAN, double_of(0xFFF8000000000000), double_of(0x7FF0000000000001), DENORM_MIN,
              -DENORM_MIN, DBL_MIN, -DBL_MIN, 1.0, -1.0, 0.5, -0.5, 2.0, 10.0, -10.0, 100.0, -100.0, 700.0, -700.0,
              709.0, -709.0, DBL_MAX, -DBL_MAX, 1e-300, 1e300, 2.0 ** -1022, math.log(2.0)):
        add(d)
    for k in range(-1074, 10, 3):
        add(math.ldexp(1.0, k))
        add(-math.ldexp(1.0, k))
    # around 2^-54, below which exp x rounds to 1 (and 2^-53, 2^-55)
    for e in (-52, -53, -54, -55, -56):
        for d in around(2.0 ** e, 3):
            add(d)
            add(-d)
    ln2 = mp.log(2)
    # thresholds: overflow, underflow to zero, the least normal result
    over = mp.mpf(2) ** 1024 - mp.mpf(2) ** 970
    x = float(mp.log(over))
    for d in around(x, 8):
        add(d)
    under = mp.mpf(2) ** -1075
    x = float(mp.log(under))
    for d in around(x, 8):
        add(d)
    x = float(mp.log(mp.mpf(2) ** -1022))
    for d in around(x, 8):
        add(d)
    for k in (-1023, -1030, -1050, -1070, -1074, 1000, 1023):
        for d in around(float(mp.log(mp.mpf(2) ** k)), 2):
            add(d)
    # results half way between two subnormals: a double rounding in the scaling would show
    for _ in range(size["exp_half"]):
        m = rng.randrange(1, 1 << 40)
        t = mp.log((mp.mpf(m) + mp.mpf(1) / 2) * mp.mpf(2) ** -1074)
        for d in around(float(t), 1):
            add(d)
    # the reduction n ln2/128 + r: r near 0 (cancellation) and near +-ln2/256 (the choice of n)
    for _ in range(size["exp_n"]):
        n = rng.randrange(-137000, 131072)
        for h in (0, 1):
            t = (mp.mpf(n) + mp.mpf(h) / 2) * ln2 / 128
            for d in around(float(t), 2):
                add(d)
    # every row of the table, at its own point and inside the cell
    for j in range(128):
        for kk in (0, rng.randrange(-1000, 1000)):
            n = j + 128 * kk
            t = mp.mpf(n) * ln2 / 128
            add(float(t))
            add(float(t) + (rng.getrandbits(53) / (1 << 53) - 0.5) * float(ln2 / 128))
    for _ in range(size["exp_uniform"]):
        add(uni(rng, -745.1332191019411, 709.782712893384))
    for _ in range(size["exp_small"]):
        add(lu(rng, 2.0 ** -60, 1.0, True))
    for _ in range(size["exp_unit"]):
        add(uni(rng, -1.0, 1.0))
    for _ in range(size["exp_sub"]):
        add(uni(rng, -745.1332191019411, -708.396))
    for _ in range(size["exp_over"]):
        add(uni(rng, 700.0, 709.782712893384))
    for w in WITNESSES["exp"]:
        add(double_of(w))
    return I.items


def log_row_value(j, offset):
    """The double with the offset bit pattern: row j, plus offset units in the last place."""
    OFF = 0x3FE6A00000000000
    return double_of(OFF + (j << 45) + offset)


def log_inputs(rng, size):
    I = Inputs(1)
    add = I.add
    for d in (0.0, -0.0, INF, -INF, QNAN, double_of(0xFFF8000000000000), double_of(0x7FF0000000000001), -1.0, -DENORM_MIN,
              -DBL_MAX, -2.0, 1.0, 2.0, 0.5, math.e, 10.0, 0.1, DBL_MIN, DBL_MAX, DENORM_MIN, 2.0 * DENORM_MIN,
              3.0 * DENORM_MIN, double_of(0x000FFFFFFFFFFFFF), math.nextafter(DBL_MIN, 0.0), math.nextafter(DBL_MAX, 0.0),
              math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.70703125):
        add(d)
    for k in range(-1074, 1024):
        add(math.ldexp(1.0, k))
    # 1 +- k ulp and 1 +- 2^-k
    for k in range(1, 60):
        for d in around(1.0 + 2.0 ** -k, 3):
            add(d)
        for d in around(1.0 - 2.0 ** -k, 3):
            add(d)
    for k in list(range(1, 400)) + [int(2.0 ** rng.uniform(8, 20)) for _ in range(size["log_ulps"])]:
        add(1.0 + k * 2.0 ** -52)
        add(1.0 - k * 2.0 ** -53)
    for _ in range(size["log_near1"]):
        r = lu(rng, 2.0 ** -52, 2.0 ** -6)
        add(1.0 + r)
        add(1.0 - r)
    # every row of the table: both edges, the middle and two random points, at the unit
    # exponent and at a random one
    for j in range(128):
        pts = [log_row_value(j, 0), log_row_value(j, (1 << 45) - 1), log_row_value(j, 1 << 44)]
        for _ in range(2):
            pts.append(log_row_value(j, rng.randrange(1 << 45)))
        for p in pts:
            add(p)
            e = rng.randrange(-1070, 1020)
            add(math.ldexp(p, e))
        for d in around(log_row_value(j, 0), 1):
            add(d)
    for d in around(1.0, 5) + around(1.0 + 2.0 ** -7, 3) + around(1.0 - 2.0 ** -8, 3) + around(0.5, 2) + around(2.0, 2):
        add(d)
    for _ in range(size["log_uniform"]):
        add(uni(rng, 0.0, 10.0))
    for _ in range(size["log_wide"]):
        add(lu(rng, 2.0 ** -1022, 2.0 ** 1023))
    for _ in range(size["log_sub"]):
        add(double_of(rng.randrange(1, 1 << 52)))
    for _ in range(size["log_mid"]):
        add(uni(rng, 0.5, 2.0))
    for w in WITNESSES["log"]:
        add(double_of(w))
    return I.items


def pow_inputs(rng, size):
    I = Inputs(2)
    add = I.add
    for x in SPECIAL_DOUBLES:
        for y in SPECIAL_DOUBLES:
            add(x, y)
    # exact results
    for base in (2.0, 3.0, 5.0, 6.0, 7.0, 10.0, 0.5, 0.25, 1.5, 1.25, -2.0, -3.0, -0.5, -10.0, 0.1, 4.0, 9.0, 16.0, 100.0):
        for n in range(-64, 65):
            add(base, float(n))
    for n in range(-1074, 1024):
        add(2.0, float(n))
        add(0.5, float(-n))
    for n in range(23, 40):
        add(10.0, float(n))
        add(-10.0, float(n))
    for x in (0.25, 4.0, 9.0, 2.25, 6.25, 0.0625, 1e-20, 1e20, 123456789.0, 1e150, 1e-150, 3.0):
        for y in (0.5, -0.5, 1.5, -1.5, 2.0, -2.0, 3.0, 0.25, -0.25, 0.75, 1.0, -1.0, 1.0 / 3.0, 2.5):
            add(x, y)
    # negative bases
    for x in (-1.0, -2.0, -0.5, -1.0000000000000002, -0.9999999999999999, -3.0, -1e-300, -1e300, -DENORM_MIN, -DBL_MAX):
        for y in (2.0 ** 53, 2.0 ** 53 - 1, 2.0 ** 52 + 1, 2.0 ** 63, 1e15 + 1, 3e20, -(2.0 ** 53), -(2.0 ** 53 - 1),
                  2.0 ** 52, 0.5, 1.5, -1.5, 1e-10, 2.0 ** 1000, 7.0, -7.0, 8.0, -8.0, 1.0, -1.0):
            add(x, y)
    for _ in range(size["pow_neg"]):
        add(-lu(rng, 2.0 ** -20, 2.0 ** 20), float(rng.randrange(-60, 60)))
    for _ in range(size["pow_neg"] // 4):
        add(-lu(rng, 2.0 ** -20, 2.0 ** 20), uni(rng, -20.0, 20.0))
    # huge exponents
    for y in (2.0 ** 62, 2.0 ** 63, 1e18, 1e300, DBL_MAX, 2.0 ** 1000, -(2.0 ** 62), -1e18, -1e300, -DBL_MAX, 2.0 ** 64,
              2.0 ** 65, 2.0 ** 64 - 4096.0):
        for x in (1.0 + 2.0 ** -52, 1.0 - 2.0 ** -53, 1.0 + 2.0 ** -40, 0.9999999999999999, 2.0, 0.5, 1e-300, 1e300, DBL_MIN,
                  DENORM_MIN, 1.0 + 2.0 ** -30, 1.0000000000000002):
            add(x, y)
    # x near 1, y chosen so that the result is of every size
    for _ in range(size["pow_near1"]):
        k = rng.uniform(4.0, 52.0)
        x = 1.0 + (1 if rng.getrandbits(1) else -1) * 2.0 ** -k
        lx = math.log(x)
        for tgt in (rng.uniform(-745.0, 709.7), rng.uniform(-3.0, 3.0), rng.uniform(300.0, 709.7), rng.uniform(-745.0, -300.0)):
            add(x, tgt / lx)
    # results near the overflow, underflow and subnormal thresholds
    thr = [709.78, 709.7827128933, 709.75, -745.13, -745.0, -744.5, -708.4, -708.3, -740.0, 700.0, -700.0, 1023.0 * math.log(2),
           -1022.0 * math.log(2), -1074.0 * math.log(2), -1074.5 * math.log(2), 1024.0 * math.log(2) - 1e-12]
    for _ in range(size["pow_edge"]):
        x = lu(rng, 2.0 ** -8, 2.0 ** 8)
        lx = math.log(x)
        if abs(lx) < 1e-2:
            continue
        t = rng.choice(thr) + rng.uniform(-1e-3, 1e-3)
        add(x, t / lx)
    for _ in range(size["pow_typ"]):
        add(lu(rng, 2.0 ** -20, 2.0 ** 20), uni(rng, -20.0, 20.0))
    for _ in range(size["pow_wide"]):
        add(lu(rng, 2.0 ** -300, 2.0 ** 300), uni(rng, -3.0, 3.0))
    for _ in range(size["pow_half"]):
        add(lu(rng, 2.0 ** -40, 2.0 ** 40), rng.randrange(-100, 100) / 2.0)
    for _ in range(size["pow_small_y"]):
        add(lu(rng, 2.0 ** -1000, 2.0 ** 1000), lu(rng, 2.0 ** -1074, 2.0 ** -3, True))
    for _ in range(size["pow_sub_x"]):
        add(double_of(rng.randrange(1, 1 << 52)), uni(rng, -2.0, 2.0))
    for _ in range(size["pow_small_int"]):
        add(lu(rng, 2.0 ** -3, 2.0 ** 3), float(rng.choice((-3, -2, -1, 1, 2, 3, 4, 5))))
    for _ in range(size["pow_pow2"]):
        add(math.ldexp(1.0, rng.randrange(-1074, 1024)), uni(rng, -1.0, 1.0))
    for w in WITNESSES["pow"]:
        add(double_of(w[0]), double_of(w[1]))
    return I.items


def atan2_inputs(rng, size):
    I = Inputs(2)
    add = I.add
    for y in SPECIAL_DOUBLES:
        for x in SPECIAL_DOUBLES:
            add(y, x)
    for _ in range(size["atan2_quad"]):
        add(lu(rng, 2.0 ** -30, 2.0 ** 30, True), lu(rng, 2.0 ** -30, 2.0 ** 30, True))
    for _ in range(size["atan2_ang"]):
        t = uni(rng, -math.pi, math.pi)
        r = lu(rng, 2.0 ** -30, 2.0 ** 30)
        add(r * math.sin(t), r * math.cos(t))
    # extreme ratios, past the range of the doubles
    for _ in range(size["atan2_ratio"]):
        a = rng.randrange(-1074, 1024)
        d = rng.randrange(-1100, 1100)
        b = max(-1074, min(1023, a - d))
        add(math.copysign(math.ldexp(1.0 + rng.getrandbits(52) / (1 << 52), a), rng.choice((-1, 1))),
            math.copysign(math.ldexp(1.0 + rng.getrandbits(52) / (1 << 52), b), rng.choice((-1, 1))))
    for _ in range(size["atan2_sub"]):
        add(math.copysign(double_of(rng.randrange(1, 1 << 52)), rng.choice((-1, 1))),
            math.copysign(lu(rng, 2.0 ** -1074, 2.0 ** -1000), rng.choice((-1, 1))))
    # near an axis, and exactly on it with a tiny offset
    for _ in range(size["atan2_axis"]):
        s = lu(rng, 2.0 ** -1000, 1e-1, True)
        o = lu(rng, 0.5, 4.0, True)
        add(s, o)
        add(o, s)
    # near the diagonal
    for _ in range(size["atan2_diag"]):
        a = lu(rng, 2.0 ** -20, 2.0 ** 20)
        k = rng.randrange(1, 64)
        for y, x in ((a, a), (a * (1 + k * 2.0 ** -52), a), (a, a * (1 + k * 2.0 ** -52)), (a * (1 + 2.0 ** -rng.randrange(8, 52)), a)):
            add(rng.choice((-1, 1)) * y, rng.choice((-1, 1)) * x)
    # every table row, the points where the nearest row changes, and the direct path's edge
    for j in range(8, 65):
        for q0 in (j / 64.0, (j + 0.5) / 64.0, (j - 0.5) / 64.0):
            for q in around(q0, 2):
                if q > 1.0 + 1e-9:
                    continue
                v = lu(rng, 0.25, 4.0)
                u = q * v
                for sy, sx in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                    if rng.getrandbits(1):
                        add(sy * u, sx * v)
                    else:
                        add(sy * v, sx * u)
        for _ in range(3):
            q = uni(rng, (j - 0.5) / 64.0, min(1.0, (j + 0.5) / 64.0))
            v = lu(rng, 2.0 ** -20, 2.0 ** 20)
            add(rng.choice((-1, 1)) * q * v, rng.choice((-1, 1)) * v)
            add(rng.choice((-1, 1)) * v, rng.choice((-1, 1)) * q * v)
    for q0 in (0.125, 2.0 ** -30, 2.0 ** -27, 1.0, 2.0 ** -10, 0.5, 2.0 ** -53):
        for q in around(q0, 6):
            v = lu(rng, 0.5, 2.0)
            add(q * v, v)
            add(v, q * v)
            add(-q * v, -v)
    for _ in range(size["atan2_direct"]):
        q = lu(rng, 2.0 ** -40, 0.125)
        v = lu(rng, 2.0 ** -20, 2.0 ** 20)
        add(rng.choice((-1, 1)) * q * v, rng.choice((-1, 1)) * v)
        add(rng.choice((-1, 1)) * v, rng.choice((-1, 1)) * q * v)
    # scaling thresholds
    for e in (600, -600, 599, 601, -599, -601, 1000, -1000, 1023, -1022, -1074):
        for d in around(math.ldexp(1.0, e), 1):
            for q in (0.5, 0.01, 1.0, 0.99999, 2.0 ** -29):
                if abs(d * q) >= DENORM_MIN or True:
                    add(d * q, d)
                    add(d, d * q)
    for _ in range(size["atan2_x1"]):
        add(lu(rng, 2.0 ** -60, 2.0 ** 60, True), 1.0)
        add(1.0, lu(rng, 2.0 ** -60, 2.0 ** 60, True))
    for w in WITNESSES["atan2"]:
        add(double_of(w[0]), double_of(w[1]))
    return I.items


def hypot_inputs(rng, size):
    I = Inputs(2)
    add = I.add
    for x in SPECIAL_DOUBLES:
        for y in SPECIAL_DOUBLES:
            add(x, y)
    triples = ((3, 4), (5, 12), (8, 15), (7, 24), (20, 21), (9, 40), (12, 35), (11, 60), (13, 84), (16, 63), (33, 56),
               (48, 55), (65, 72), (28, 45), (36, 77), (39, 80), (119, 120), (4, 3), (12, 5))
    for a, b in triples:
        for k in range(-1000, 1001, 37):
            s = math.ldexp(1.0, k)
            add(a * s, b * s)
            add(-a * s, b * s)
        for m in (3, 5, 7, 9, 11, 101, 1001, 12345, 3 ** 20):
            add(float(a * m), float(b * m))
        add(a * 1e150, b * 1e150)
        add(a * 1e-150, b * 1e-150)
    for e in (1023, 1022, 1000, 600, 300, 299, 301, -300, -299, -301, -600, -1000, -1022, -1073, -1074):
        for d in around(math.ldexp(1.0, e), 2):
            for q in (1.0, 0.99999999, 0.5, 0.3, 2.0 ** -20, 2.0 ** -26, 2.0 ** -27, 2.0 ** -28, 2.0 ** -29, 2.0 ** -60):
                add(d, d * q)
                add(d * q, d)
    s = DBL_MAX / math.sqrt(2.0)
    for d in around(s, 6):
        add(d, d)
        add(d, -d)
    for d in around(DBL_MAX, 2):
        add(d, DBL_MAX)
        add(d, 1e292)
        add(d, 1e291)
        add(d, 1.0)
    for d in around(DBL_MIN, 3):
        add(d, d)
        add(d, DENORM_MIN)
    for k in range(1, 6):
        add(k * DENORM_MIN, DENORM_MIN)
        add(k * DENORM_MIN, k * DENORM_MIN)
        add(k * DENORM_MIN, 2 * DENORM_MIN)
    for _ in range(size["hypot_ang"]):
        t = uni(rng, 0.0, math.pi / 2)
        r = lu(rng, 2.0 ** -30, 2.0 ** 30)
        add(r * math.cos(t), r * math.sin(t))
    for _ in range(size["hypot_ratio"]):
        a = lu(rng, 2.0 ** -500, 2.0 ** 500, True)
        add(a, a * uni(rng, 0.05, 1.0))
    for _ in range(size["hypot_spread"]):
        add(lu(rng, 2.0 ** -1070, 2.0 ** 1022, True), lu(rng, 2.0 ** -1070, 2.0 ** 1022, True))
    for _ in range(size["hypot_exp"]):
        a = lu(rng, 2.0 ** -300, 2.0 ** 300)
        add(a, a * 2.0 ** -rng.uniform(20.0, 35.0))
    for _ in range(size["hypot_near"]):
        a = lu(rng, 2.0 ** -300, 2.0 ** 300)
        add(a, math.nextafter(a, 0.0) if rng.getrandbits(1) else a * (1 + rng.randrange(1, 30) * 2.0 ** -52))
    for _ in range(size["hypot_scaled"]):
        a = lu(rng, 2.0 ** -30, 2.0 ** 30)
        add(a * 2.0 ** rng.choice((-1000, 1000, 500, -500, 300, -300)), a * uni(rng, 0.1, 1.0) * 2.0 ** rng.choice((-1000, 1000, 500, -500, 300, -300)))
    for w in WITNESSES["hypot"]:
        add(double_of(w[0]), double_of(w[1]))
    return I.items


COMMITTED = dict(exp_half=60, exp_n=300, exp_uniform=1500, exp_small=600, exp_unit=300, exp_sub=500, exp_over=300,
                 log_ulps=300, log_near1=800, log_uniform=500, log_wide=1500, log_sub=500, log_mid=500,
                 pow_neg=500, pow_near1=250, pow_edge=900, pow_typ=2500, pow_wide=1000, pow_half=400, pow_small_y=300,
                 pow_sub_x=200, pow_small_int=300, pow_pow2=200,
                 atan2_quad=1500, atan2_ang=1500, atan2_ratio=1000, atan2_sub=300, atan2_axis=500, atan2_diag=150,
                 atan2_direct=500, atan2_x1=150,
                 hypot_ang=1500, hypot_ratio=700, hypot_spread=1200, hypot_exp=500, hypot_near=500, hypot_scaled=400)
FRESH = dict(exp_half=8, exp_n=40, exp_uniform=500, exp_small=200, exp_unit=100, exp_sub=150, exp_over=100,
             log_ulps=40, log_near1=250, log_uniform=250, log_wide=500, log_sub=150, log_mid=200,
             pow_neg=120, pow_near1=60, pow_edge=250, pow_typ=900, pow_wide=350, pow_half=150, pow_small_y=100,
             pow_sub_x=60, pow_small_int=100, pow_pow2=60,
             atan2_quad=500, atan2_ang=500, atan2_ratio=350, atan2_sub=100, atan2_axis=150, atan2_diag=40,
             atan2_direct=200, atan2_x1=50,
             hypot_ang=500, hypot_ratio=250, hypot_spread=400, hypot_exp=150, hypot_near=150, hypot_scaled=120)


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
    mp.prec = 640
    gens = (("exp", exp_inputs), ("log", log_inputs), ("pow", pow_inputs), ("atan2", atan2_inputs), ("hypot", hypot_inputs))
    for fn, gen in gens:
        r2 = random.Random(a.seed * 1000003 + sum(map(ord, fn)))
        inputs = gen(r2, size)
        kinds = {}
        lines = []
        for args in inputs:
            line, kind = entry(fn, args)
            lines.append(line)
            kinds[kind] = kinds.get(kind, 0) + 1
        with open(os.path.join(a.out, fn + ".corpus"), "w") as f:
            f.write("# %s corpus for gmath_%s, from tools/oracle/gen_corpus_elem.py\n" % (fn, fn))
            f.write("# oracle: %s\n" % prov)
            f.write("# seed %d size %s entries %d\n" % (a.seed, a.size, len(lines)))
            if fn in ("exp", "log"):
                f.write("# x_bits r_bits err_bits: r correctly rounded, err = (exact - r)/ulp(exact) as an IEEE single\n")
            else:
                f.write("# a_bits b_bits r_bits err_bits (atan2: y then x; pow: x then y; hypot: x then y): r correctly rounded, err = (exact - r)/ulp(exact) as an IEEE single\n")
            f.write("\n".join(lines) + "\n")
        sys.stderr.write("%s: %d entries %s\n" % (fn, len(lines), sorted(kinds.items())))


main()
