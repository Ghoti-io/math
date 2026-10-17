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
"""Write the sin, cos and tan corpus files for gmath_sin, gmath_cos, gmath_tan.

Runs in the pinned oracle image (tools/oracle/oracle.py corpus|fresh).  Each
line of <fn>.corpus is three fields, hexadecimal and fixed width:

    x_bits (16)   r_bits (16)   err_bits (8)

x is the input double.  r is the correctly rounded (to nearest, ties to even)
double of the exact value of fn(x), computed by MPFR (gmpy2) at 600 + exponent
bits and rounded once, exactly, by Python's correctly rounded int/int division.
err is the IEEE single whose value is (exact - r) / ulp(exact), the signed
distance of the exact value from r in units of the spacing of doubles at the
exact value (2^-1074 below 2^-1022).  With that, a result y is within 1 ulp of
the exact value iff |((y - r) / ulp) - err| <= 1, which the test evaluates
without needing the exact value itself.  A NaN result is r = 7ff8000000000000
with err 0 (the test accepts any NaN).

Every entry is also computed with mpmath, a separate implementation, and the
two must agree to 2^-400 relative; the run fails otherwise.  The printed
statistics say how many entries sit near a rounding tie, near a multiple of
pi/2, and so on, so that a corpus which has stopped covering a case shows.

The inputs, by category (the same inputs for all three functions):

  special   +-0, +-inf, NaNs, subnormals, DBL_MIN, DBL_MAX, powers of two,
            pi/4 and its neighbours
  uniform   random in [-1e5, 1e5]
  small     random magnitude 2^-60 .. 2^20
  bits      random finite bit patterns, every exponent (most are huge)
  kpi2      the double nearest k*pi/2, and its neighbours, for small and for
            huge random k
  cf        for each binary exponent, the doubles whose x*2/pi is nearest an
            integer, found from the continued fraction of 2^q * 2/pi (the
            worst cases for argument reduction)
  cw        the edges of the fast reduction for |x| < 2^20 (src/elementary/
            trig.c, reduce_fast): the doubles either side of 2^20, near k*pi/2
            for small k and for k up to the largest it handles, at the offsets
            where its remainder is anywhere from 2^-62 to 2^-24 (the floor
            under which it hands over to the exact reduction is 2^-55), and
            near (k + 1/2) * pi/2 where its quotient is the least certain.
            k goes past the 2^20 limit to 32 times it, so that a limit set
            too high is seen.  Appended after every category above, so the
            earlier entries of a given seed are the same as before it existed.
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


def bits_of(d):
    return struct.unpack(">Q", struct.pack(">d", d))[0]


def double_of(u):
    return struct.unpack(">d", struct.pack(">Q", u))[0]


def prec_for(x):
    e = math.frexp(x)[1] if x != 0 and math.isfinite(x) else 0
    return 600 + max(0, e)


def exact_value(fn, x):
    """MPFR's value of fn(x) at 600 + exponent bits."""
    with gmpy2.context(precision=prec_for(x), emin=EMIN, emax=EMAX):
        xm = gmpy2.mpfr(x)
        return getattr(gmpy2, fn)(xm)


def mp_value(fn, x):
    """mpmath's value, as (mantissa, exponent), at the same precision."""
    mp.prec = prec_for(x)
    v = getattr(mp, fn)(mp.mpf(x))
    return v


def to_fraction(v):
    n, d = v.as_integer_ratio()
    return Fraction(int(n), int(d))


def ulp_exp(frac):
    """Exponent of the spacing of doubles at the value frac (nonzero)."""
    a = abs(frac)
    k = a.numerator.bit_length() - a.denominator.bit_length()
    if a < Fraction(2) ** k:
        k -= 1
    return max(k, -1022) - 52


def entry(fn, x):
    """The corpus line for fn(x), after checking MPFR against mpmath."""
    if math.isnan(x) or math.isinf(x):
        return "%016x %016x %08x" % (bits_of(x), 0x7FF8000000000000, 0), "nonfinite"
    v = exact_value(fn, x)
    if v == 0:
        r = float(v)
        return "%016x %016x %08x" % (bits_of(x), bits_of(r), 0), "zero"
    ex = to_fraction(v)
    # Cross-check against the second implementation.
    w = mp_value(fn, x)
    wm = mp.mpf(w)
    vm = mp.mpf(int(v.as_integer_ratio()[0])) / mp.mpf(int(v.as_integer_ratio()[1]))
    if abs(wm - vm) > abs(vm) * mp.mpf(2) ** -400:
        raise SystemExit("MPFR and mpmath disagree on %s(%r): %s vs %s" % (fn, x, v, wm))
    r = ex.numerator / ex.denominator  # int / int is correctly rounded
    rf = Fraction(r)
    err = (ex - rf) / Fraction(2) ** ulp_exp(ex)
    e32 = struct.unpack(">I", struct.pack(">f", err.numerator / err.denominator))[0]
    kind = "tie" if abs(err) > Fraction(49, 100) else "normal"
    return "%016x %016x %08x" % (bits_of(x), bits_of(r), e32), kind


def finite(d):
    return math.isfinite(d)


def cf_cases(q, pi_over_2_inv):
    """Doubles x = m * 2^q, m in [2^52, 2^53), with m * 2^q * 2/pi nearest an
    integer: the best two found among the multiples of the continued fraction
    convergents' denominators."""
    alpha = (pi_over_2_inv * Fraction(2) ** q) % 1
    lo, hi = 1 << 52, 1 << 53
    # Continued fraction of alpha.
    cands = []
    p0, q0, p1, q1 = 0, 1, 1, 0  # convergents p_{-2}/q_{-2} and p_{-1}/q_{-1}
    x = alpha
    for _ in range(200):
        a = x.numerator // x.denominator
        p0, q0, p1, q1 = p1, q1, a * p1 + p0, a * q1 + q0
        if q1 > hi:
            break
        delta = abs(q1 * alpha - p1)
        j = -(-lo // q1)
        for jj in (j, j + 1):
            m = jj * q1
            if lo <= m < hi:
                cands.append((jj * delta, m))
        frac = x - a
        if frac == 0:
            break
        x = 1 / frac
    cands.sort()
    out = []
    for _, m in cands:
        if m not in out:
            out.append(m)
        if len(out) == 2:
            break
    return [math.ldexp(float(m), q) for m in out]


def cw_inputs(rng, PI, add, n_k):
    """Edge cases of the fast reduction (see the module docstring)."""
    L = 2.0 ** 20
    for s in (1.0, -1.0):
        for base in (L, L / 2, L * 2):
            d = base
            for _ in range(8):
                d = math.nextafter(d, 0)
                add(s * d)
            d = base
            add(s * d)
            for _ in range(8):
                d = math.nextafter(d, math.inf)
                add(s * d)
    for _ in range(60):
        e = rng.uniform(19.0, 22.0)
        add((1 if rng.getrandbits(1) else -1) * 2.0 ** e)
    kmax = int(L * 2 / math.pi) + 1
    ks = list(range(1, 9)) + list(range(kmax - 4, kmax + 3))
    for _ in range(n_k):
        ks.append(int(2.0 ** rng.uniform(0, math.log2(kmax))))
    for _ in range(n_k // 2):
        ks.append(int(2.0 ** rng.uniform(math.log2(kmax) - 1, math.log2(kmax * 32))))
    for k in ks:
        t = float(PI * k / 2)
        if not (math.pi / 4 < t < 64 * L):
            continue
        d = t
        for _ in range(3):
            d = math.nextafter(d, 0)
            add(d)
        d = t
        add(d)
        for _ in range(3):
            d = math.nextafter(d, math.inf)
            add(d)
        u = math.ulp(t)
        for e in range(-62, -23, 2):
            j = max(1, round(2.0 ** e / u))
            add(t + j * u)
            add(t - j * u)
        h = float(PI * (2 * k + 1) / 4)
        d = h
        for _ in range(3):
            d = math.nextafter(d, 0)
        for _ in range(7):
            add(d)
            d = math.nextafter(d, math.inf)


def gen_inputs(rng, n_uniform, n_small, n_bits, n_kpi2_small, n_kpi2_big, cf_step, n_cw_k):
    seen = set()
    inputs = []

    def add(d):
        b = bits_of(d)
        if b not in seen:
            seen.add(b)
            inputs.append(d)

    # special
    for u in (0x0, 0x8000000000000000, 0x7FF0000000000000, 0xFFF0000000000000,
              0x7FF8000000000000, 0xFFF8000000000000, 0x7FF0000000000001,
              0x7FF8000000000123, 0x0000000000000001, 0x8000000000000001,
              0x0000000000000002, 0x0000000000000003, 0x000FFFFFFFFFFFFF,
              0x800FFFFFFFFFFFFF, 0x0010000000000000, 0x8010000000000000,
              0x0010000000000001, 0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF,
              0x7FEFFFFFFFFFFFFE, 0x7FE0000000000000):
        add(double_of(u))
    for k in range(-1074, 1024, 3):
        add(math.ldexp(1.0, k))
        add(-math.ldexp(1.0, k))
    pio4 = math.pi / 4
    for d in (pio4, math.nextafter(pio4, 0), math.nextafter(pio4, 2), math.pi / 2,
              math.pi, 1.0, 2.0, 3.0, 0.5, 1e-9, 2.0 ** -27, 2.0 ** -28,
              math.nextafter(2.0 ** -28, 0), math.nextafter(2.0 ** -28, 1),
              math.nextafter(2.0 ** -27, 0), math.nextafter(2.0 ** -27, 1)):
        for s in (1.0, -1.0):
            add(s * d)
    # uniform
    for _ in range(n_uniform):
        add((rng.getrandbits(53) / (1 << 53) * 2 - 1) * 1e5)
    # small magnitude
    for _ in range(n_small):
        e = rng.randrange(-60, 21)
        m = 1.0 + rng.getrandbits(52) / (1 << 52)
        add((1 if rng.getrandbits(1) else -1) * math.ldexp(m, e))
    # random finite bit patterns
    got = 0
    while got < n_bits:
        u = rng.getrandbits(64)
        d = double_of(u)
        if finite(d):
            add(d)
            got += 1
    # nearest to k pi/2 (needs pi to more bits than any k we use)
    num, den = gmpy2.const_pi(precision=4096).as_integer_ratio()
    PI = Fraction(int(num), int(den))
    for k in range(1, n_kpi2_small + 1):
        t = float(PI * k / 2)
        for d in (math.nextafter(t, 0), t, math.nextafter(t, math.inf)):
            add(d)
            add(-d)
    for _ in range(n_kpi2_big):
        k = rng.getrandbits(rng.randrange(20, 1020))
        if k == 0:
            continue
        t = float(PI * k / 2)
        if not finite(t):
            continue
        for d in (math.nextafter(t, 0), t, math.nextafter(t, math.inf)):
            if finite(d):
                add(d)
    # continued-fraction worst cases for the reduction, every cf_step-th exponent
    inv = 2 / PI
    for q in range(-53, 972, cf_step):
        for d in cf_cases(q, inv):
            if finite(d):
                add(d)
    # the fast reduction's edges, last so that nothing above moves
    cw_inputs(rng, PI, add, n_cw_k)
    return inputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--size", choices=("committed", "fresh"), default="committed")
    a = ap.parse_args()
    if a.size == "committed":
        sizes = dict(n_uniform=4000, n_small=2000, n_bits=3500, n_kpi2_small=250,
                     n_kpi2_big=350, cf_step=1, n_cw_k=40)
    else:
        sizes = dict(n_uniform=600, n_small=300, n_bits=500, n_kpi2_small=40,
                     n_kpi2_big=60, cf_step=7, n_cw_k=12)
    rng = random.Random(a.seed)
    inputs = gen_inputs(rng, **sizes)
    os.makedirs(a.out, exist_ok=True)
    prov = "mpfr %s gmpy2 %s mpmath %s python %d.%d.%d" % (
        gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__,
        *sys.version_info[:3])
    for fn in ("sin", "cos", "tan"):
        kinds = {}
        lines = []
        for x in inputs:
            line, kind = entry(fn, x)
            lines.append(line)
            kinds[kind] = kinds.get(kind, 0) + 1
        with open(os.path.join(a.out, fn + ".corpus"), "w") as f:
            f.write("# %s corpus for gmath_%s, from tools/oracle/gen_corpus.py\n" % (fn, fn))
            f.write("# oracle: %s\n" % prov)
            f.write("# seed %d size %s entries %d\n" % (a.seed, a.size, len(lines)))
            f.write("# x_bits r_bits err_bits: r correctly rounded, err = (exact - r)/ulp(exact) as an IEEE single\n")
            f.write("\n".join(lines) + "\n")
        sys.stderr.write("%s: %d entries %s\n" % (fn, len(lines), sorted(kinds.items())))


main()
