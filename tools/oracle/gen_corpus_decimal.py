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
"""Write the corpus files of gmath_decimal_parse (decimal_parse.corpus) and
gmath_decimal_shortest (decimal_shortest.corpus).

Runs in the pinned oracle image (tools/oracle/oracle.py corpus|fresh), after
the other generators.  Both functions have one correct answer, so the test
requires the library's result to equal it exactly:

    decimal_parse     text  r_bits  flags          (flags: 1 inexact, 2 overflow,
                                                    4 underflow, tininess before
                                                    rounding)
    decimal_shortest  x_bits  digits  exponent     (x = digits * 10^exponent, the
                                                    sign from x_bits; zero is 0 0)

The text of a parse line is a whole number in the grammar of decimal.h, with
no space in it, so the line splits on spaces.

How each answer is made, and what it is checked against (the run fails if two
disagree):

  parse     the exact rational value of the text, read by a parser written here,
            rounded by Python's correctly rounded int / int with the overflow and
            underflow thresholds of binary64 written here, and the flags from the
            exact comparison of that result with the value; against MPFR
            (mpfr_set_str at 53 bits with binary64's exponent range and
            subnormals) and CPython's float(), which must give the same bits.
            A text whose exponent is too large for an exact rational is decided
            from the power of ten of its leading digit (10^309 and above is
            infinity, below 10^-324 is zero), against MPFR and float() alike.
  shortest  an exact search written here: for n = 1 .. 17 significant digits,
            the integers inside the rational interval of decimals that round to
            x (ends included when x's significand is even), the one nearest x,
            half to even; against CPython's repr(), whose digits must round-trip
            and be as few, and which must equal the search wherever repr's
            choice is the nearest.

The inputs (see the functions below):

  parse     the shortest spellings and longer spellings of random doubles; the
            exact decimal expansions of the midpoints between two doubles (the
            ties, to even and away), and of decimals just above and just below
            them, written with more than 800 significant digits; the overflow
            threshold, the smallest subnormal and half of it, the normal
            boundary; integers around 2^53 and 2^64; leading and trailing zeros,
            zeros of both signs, huge exponents of both signs; fraction lengths
            that put the divisor in one 32-bit limb and in more
  shortest  random bit patterns of both signs, every power of two, the
            neighbours of powers of two and ten, subnormals of every bit length,
            integers up to and beyond 2^53, the extremes
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

M64 = (1 << 64) - 1
TWO = Fraction(2)
OVERFLOW_AT = TWO ** 1024 - TWO ** 970  # the midpoint above the largest double
SUBNORMAL_HALF = TWO ** -1075
NORMAL_MIN = TWO ** -1022

COMMITTED = dict(random_doubles=6000, spellings=4000, midpoints=500, shortest_random=12000)
FRESH = dict(random_doubles=600, spellings=400, midpoints=250, shortest_random=1200)


def bits_of(d):
    return struct.unpack(">Q", struct.pack(">d", d))[0]


def double_of(u):
    return struct.unpack(">d", struct.pack(">Q", u))[0]


def frac_of(u):
    """The exact value of a finite double, from its bits."""
    s = -1 if u >> 63 else 1
    e = (u >> 52) & 0x7FF
    m = u & ((1 << 52) - 1)
    if e == 0:
        return s * Fraction(m) * TWO ** -1074
    return s * Fraction((1 << 52) | m) * TWO ** (e - 1075)


def finite_bits(rng):
    while True:
        u = rng.getrandbits(64)
        if (u >> 52) & 0x7FF != 0x7FF:
            return u


# ---------------------------------------------------------------------------
# Parse: the answer
# ---------------------------------------------------------------------------

def split_text(s):
    """(negative, digits, power of ten of the last digit), by the grammar of
    decimal.h, written here independently of the library."""
    i = 0
    neg = False
    if s[i] in "+-":
        neg = s[i] == "-"
        i += 1
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    ip = s[i:j]
    fp = ""
    if j < len(s) and s[j] == ".":
        k = j + 1
        while k < len(s) and s[k].isdigit():
            k += 1
        fp = s[j + 1:k]
        j = k
    assert ip or fp
    e = 0
    if j < len(s) and s[j] in "eE":
        e = int(s[j + 1:])
        j = len(s)
    assert j == len(s), s
    return neg, ip + fp, e - len(fp)


def round_rational(a):
    """The nearest-even double of a positive rational, with binary64's
    thresholds, and the flags."""
    if a >= OVERFLOW_AT:
        return math.inf, 1 | 2
    if a <= SUBNORMAL_HALF:
        return 0.0, 1 | 4
    r = a.numerator / a.denominator  # correctly rounded, subnormals included
    flags = 0
    if Fraction(r) != a:
        flags |= 1
        if a < NORMAL_MIN:
            flags |= 4
    return r, flags


def parse_answer(s):
    neg, digits, e = split_text(s)
    stripped = digits.lstrip("0")
    if not stripped:
        r, flags = 0.0, 0
    else:
        lead = e + len(stripped) - 1
        if lead >= 309:
            r, flags = math.inf, 1 | 2
        elif lead <= -325:
            r, flags = 0.0, 1 | 4
        else:
            v = Fraction(int(stripped)) * Fraction(10) ** e
            r, flags = round_rational(v)
    if neg:
        r = -r
    u = bits_of(r)
    # MPFR, with binary64's exponent range and subnormals.
    ctx = gmpy2.context(precision=53, emin=-1073, emax=1024, subnormalize=True,
                        round=gmpy2.RoundToNearest)
    with gmpy2.context(ctx):
        m = gmpy2.mpfr(s)
        m = gmpy2.check_range(m)
    mu = bits_of(float(m))
    if mu != u:
        raise SystemExit("decimal_parse: MPFR says %016x for %r, the exact reference %016x" % (mu, s, u))
    fu = bits_of(float(s))
    if fu != u:
        raise SystemExit("decimal_parse: float() says %016x for %r, the exact reference %016x" % (fu, s, u))
    return u, flags


# ---------------------------------------------------------------------------
# Parse: the inputs
# ---------------------------------------------------------------------------

def exact_decimal(fr):
    """The exact decimal spelling of a nonnegative dyadic rational."""
    n, d = fr.numerator, fr.denominator
    k = 0
    while d != 1:
        assert d % 2 == 0
        d //= 2
        n *= 5
        k += 1
    return "%de-%d" % (n, k) if k else str(n)


def long_decimal(fr, sig):
    """A decimal of exactly `sig` significant digits within 10^-(sig-1) relative
    of fr, plus the flag whether it is fr exactly."""
    if fr == 0:
        return "0"
    e = 0
    while Fraction(10) ** (e + 1) <= fr:
        e += 1
    while Fraction(10) ** e > fr:
        e -= 1
    scale = sig - 1 - e
    n = (fr * Fraction(10) ** scale).numerator // (fr * Fraction(10) ** scale).denominator
    return "%de%d" % (n, -scale)


def parse_inputs(rng, size):
    out = []
    fixed = [
        "0", "-0", "+0", "0.0", "-0.000", ".0", "0.", "0e999999999999999999999",
        "-0e-999999999999999999999", "000000000000000000000001", "1.000000000000000000000",
        "1", "-1", "+1", ".5", "5.", "1e0", "1E+0", "1e-0",
        "0.1", "0.2", "0.3", "1e23", "8.589973e9", "9007199254740992", "9007199254740993",
        "9007199254740994", "9007199254740995", "18446744073709551615", "18446744073709551616",
        "1.7976931348623157e308", "1.7976931348623158e308", "1.7976931348623159e308",
        "179769313486231580793728971405303415079934132710037826936173778980444968292764750946649017977587207096330286416692887910946555547851940402630657488671505820681908902000708383676273854845817711531764475730270069855571366959622842914819860834936475292719074168444365510704342711559699508093042880177904174497791",
        "1e308", "1.8e308", "2e308", "3.5e308", "-2.5e308", "1e309", "-1e309", "9.999999999999999e308", "1e310", "1e400",
        "2.2250738585072014e-308", "2.2250738585072011e-308", "2.2250738585072012e-308",
        "4.9406564584124654e-324", "5e-324", "2.4703282292062327e-324", "2.4703282292062328e-324",
        "2.47032822920623272e-324", "1e-324", "1e-325", "-1e-400",
        "1e999999999999999999999999999", "1e-999999999999999999999999999",
        "0." + "0" * 400 + "1e400", "1" + "0" * 400 + "e-400",
        "1" * 1000, "0." + "1" * 1000, "9" * 900 + "e-600",
        "123456789012345678901234567890.5", "0.000001", "0.0000000001", "1234.5678",
    ]
    out.extend(fixed)
    # Ties broken by digits the division's remainder holds, in each division
    # tier: the midpoint above 2^k as an integer, followed by a short fraction
    # (a divisor of one limb) and a long one (restoring division), and the
    # midpoints themselves (ties to even, upward and downward).
    for k in range(53, 64):
        mid_int = (1 << k) + (1 << (k - 53))
        for tail in ("", ".000000001", ".5", "." + "0" * 15 + "1", "." + "0" * 40 + "1"):
            out.append(str(mid_int) + tail)
            out.append(str(mid_int + 2 * (1 << (k - 52)) ) + tail)
        out.append(str(mid_int - 1) + "." + "9" * 9)
        out.append(str(mid_int - 1) + "." + "9" * 30)
    # The midpoint above the largest double, exactly, and either side.
    mid = OVERFLOW_AT
    out.append(exact_decimal(mid))
    out.append(exact_decimal(mid) + ".000000000000000000000000000000000000001")
    out.append(long_decimal(mid - TWO ** 900, 900))
    out.append(exact_decimal(SUBNORMAL_HALF))
    out.append(long_decimal(SUBNORMAL_HALF * (1 + Fraction(1, 10 ** 820)), 850))
    out.append(long_decimal(SUBNORMAL_HALF * (1 - Fraction(1, 10 ** 820)), 850))
    for _ in range(size["random_doubles"]):
        x = double_of(finite_bits(rng))
        out.append(repr(x).replace("inf", "1e400"))
    for _ in range(size["spellings"]):
        x = double_of(finite_bits(rng))
        p = rng.randint(0, 40)
        s = "%.*e" % (p, x)
        out.append(s)
        out.append("%.*f" % (rng.randint(0, 30), x) if abs(x) < 1e30 else s)
        # Short fixed-point decimals, the shape SVG and CSS write, by fraction length.
        n = rng.randint(1, 30)
        out.append("%d.%0*d" % (rng.randint(0, 99999), n, rng.randint(0, 10 ** n - 1)))
    for _ in range(size["midpoints"]):
        kind = rng.randrange(4)
        if kind == 0:
            u = rng.randrange(1, 1 << 52)  # subnormal
        elif kind == 1:
            u = rng.randrange(0x7FE0000000000000, 0x7FEFFFFFFFFFFFFF)
        else:
            u = rng.getrandbits(62)
        a = frac_of(u)
        b = frac_of(u + 1)
        m = (a + b) / 2
        out.append(exact_decimal(m))
        eps = Fraction(1, 10 ** rng.randint(780, 860))
        out.append(long_decimal(m * (1 + eps), rng.randint(801, 900)))
        out.append(long_decimal(m * (1 - eps), rng.randint(801, 900)))
        out.append(exact_decimal(a))
    return out


# ---------------------------------------------------------------------------
# Shortest
# ---------------------------------------------------------------------------

def shortest_answer(u):
    x = frac_of(u)
    if x == 0:
        return "0", 0
    ax = abs(x)
    e = (u >> 52) & 0x7FF
    m = u & ((1 << 52) - 1)
    ulp = TWO ** (-1074 if e == 0 else e - 1075)
    lo = ax - ulp / 2
    if m == 0 and e > 1:
        lo = ax - ulp / 4
    hi = ax + ulp / 2
    sig = (m if e == 0 else m | (1 << 52))
    inclusive = sig % 2 == 0
    L = 0
    while Fraction(10) ** (L + 1) <= ax:
        L += 1
    while Fraction(10) ** L > ax:
        L -= 1
    for n in range(1, 18):
        s = L - n + 1
        p = Fraction(10) ** s
        a, b, c = lo / p, hi / p, ax / p
        clo = math.ceil(a)
        if clo == a and not inclusive:
            clo += 1
        chi = math.floor(b)
        if chi == b and not inclusive:
            chi -= 1
        if clo > chi:
            continue
        fl = math.floor(c)
        rem = c - fl
        if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
            fl += 1
        cand = min(max(fl, clo), chi)
        while cand % 10 == 0:
            cand //= 10
            s += 1
        return str(cand), s
    raise SystemExit("decimal_shortest: no candidate for %016x" % u)


def shortest_check(u, digits, exp):
    x = double_of(u)
    if x == 0:
        if (digits, exp) != ("0", 0):
            raise SystemExit("decimal_shortest: zero written as %se%d" % (digits, exp))
        return
    back = float(digits + "e" + str(exp))
    if bits_of(back) != (u & 0x7FFFFFFFFFFFFFFF):
        raise SystemExit("decimal_shortest: %se%d does not round to %016x" % (digits, exp, u))
    r = repr(abs(x))
    mant, _, ex = r.partition("e")
    ex = int(ex) if ex else 0
    if "." in mant:
        ip, fp = mant.split(".")
    else:
        ip, fp = mant, ""
    rd = (ip + fp).lstrip("0")
    rexp = ex - len(fp)
    while rd.endswith("0") and rd != "0":
        rd = rd[:-1]
        rexp += 1
    if len(rd) != len(digits):
        raise SystemExit("decimal_shortest: repr gives %d digits (%s) for %016x, the search %d (%s)"
                         % (len(rd), r, u, len(digits), digits))
    if rd != digits or rexp != exp:
        dr = abs(Fraction(int(rd)) * Fraction(10) ** rexp - abs(frac_of(u)))
        ds = abs(Fraction(int(digits)) * Fraction(10) ** exp - abs(frac_of(u)))
        if ds > dr:
            raise SystemExit("decimal_shortest: repr's %se%d is nearer than %se%d for %016x"
                             % (rd, rexp, digits, exp, u))


def shortest_inputs(rng, size):
    us = [0, 1 << 63, 1, 2, 3, 0x000FFFFFFFFFFFFF, 0x0010000000000000, 0x0010000000000001,
          0x7FEFFFFFFFFFFFFF, 0x7FEFFFFFFFFFFFFE, 0x3FF0000000000000, 0x3FEFFFFFFFFFFFFF,
          0x3FF0000000000001, bits_of(0.1), bits_of(0.3), bits_of(1e23), bits_of(5e-324),
          bits_of(2.0 ** 53), bits_of(2.0 ** 53 + 2), bits_of(2.0 ** 53 - 1), bits_of(2.0 ** 54),
          bits_of(123456789012345678.0), bits_of(9007199254740993.0)]
    for e in range(1, 2047):  # every power of two, and its neighbours
        u = e << 52
        us += [u, u - 1, u + 1]
    for k in range(-323, 309):  # the doubles nearest the powers of ten, and their neighbours
        u = bits_of(float("1e%d" % k))
        if u:
            us += [u, u - 1, u + 1]
    for b in range(1, 53):  # subnormals of every bit length
        us.append(rng.randrange(1 << (b - 1), 1 << b))
    for n in range(0, 2000):  # integers past 2^54, whose interval ends are even integers
        us.append(bits_of(float((1 << 54) + 4 * n)))
        us.append(bits_of(float((1 << 55) + 8 * n)))
    for n in range(0, 2000):  # integers around zero and 2^53
        us.append(bits_of(float(n)))
        us.append(bits_of(float((1 << 53) - n)))
        us.append(bits_of(float((1 << 53) + 2 * n)))
    for _ in range(size["shortest_random"]):
        us.append(finite_bits(rng))
        us.append(bits_of(rng.uniform(-1e6, 1e6)))
    seen = set()
    out = []
    for u in us:
        if u not in seen and (u >> 52) & 0x7FF != 0x7FF:
            seen.add(u)
            out.append(u)
    return out


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
            f.write("# %s corpus for gmath_%s, from tools/oracle/gen_corpus_decimal.py\n" % (fn, fn))
            f.write("# oracle: %s\n" % prov)
            f.write("# seed %d size %s entries %d\n" % (a.seed, a.size, len(lines)))
            f.write("# %s: the answer is exact, the test requires the result to equal it\n" % desc)
            f.write("\n".join(lines) + "\n")
        sys.stderr.write("%s: %d entries\n" % (fn, len(lines)))

    lines = []
    seen = set()
    for s in parse_inputs(rng_for("decimal_parse"), size):
        if s in seen:
            continue
        seen.add(s)
        u, flags = parse_answer(s)
        lines.append("%s %016x %d" % (s, u, flags))
    write("decimal_parse", "text r_bits flags", lines)

    lines = []
    for u in shortest_inputs(rng_for("decimal_shortest"), size):
        digits, exp = shortest_answer(u)
        shortest_check(u, digits, exp)
        lines.append("%016x %s %d" % (u, digits, exp))
    write("decimal_shortest", "x_bits digits exponent", lines)


main()
