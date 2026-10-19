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
  kernel    the table-driven kernel (src/elementary/trig.c, kernel_front): for
            every table row a reduced argument can reach (a = 2^e (1 + s/64) up
            to pi/4, 229 rows) the double a itself, the double just below the
            next row, and two random points between, as an unreduced argument
            (the even quadrants) and the same reduced argument made odd by
            adding pi/2 (cos for sin, cot for tan); the neighbours of 2^-4,
            where the table starts and the direct polynomial ends; the direct
            path's odd quadrant (cot of a small remainder) at every binade;
            and the KERNEL_WITNESSES below.  Appended last, as above.
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


def cw2_inputs(rng, PI, add, n_k, inv):
    """Edge cases of the wide fast reduction, 2^20 <= |x| < 2^30 (trig.c,
    reduce_fast_wide): the doubles either side of its limit 2^30 and of 2^29,
    the doubles of each binade nearest a multiple of pi/2 (the cancellation
    that hurts most, down to 2^-59), and doubles at and around k*pi/2 for k
    spread over the whole range up to the quotient limit 2^30 * 2/pi."""
    L = 2.0 ** 30
    for s in (1.0, -1.0):
        for base in (L, L / 2):
            d = base
            for _ in range(8):
                d = math.nextafter(d, 0)
                add(s * d)
            d = base
            for _ in range(8):
                d = math.nextafter(d, math.inf)
                add(s * d)
        for e in range(20, 30):
            for d in cf_cases(e - 52, inv):
                add(s * d)
                add(s * math.nextafter(d, 0))
                add(s * math.nextafter(d, math.inf))
    kmin = int(2.0 ** 20 * 2 / math.pi)
    kmax = int(L * 2 / math.pi)
    ks = list(range(kmin - 2, kmin + 3)) + list(range(kmax - 4, kmax + 3))
    for _ in range(n_k * 2):
        ks.append(int(2.0 ** rng.uniform(math.log2(kmin), math.log2(kmax))))
    for k in ks:
        t = float(PI * k / 2)
        if not (2.0 ** 20 <= t < L):
            continue
        d = t
        add(d)
        for _ in range(2):
            d = math.nextafter(d, 0)
            add(d)
        d = t
        for _ in range(2):
            d = math.nextafter(d, math.inf)
            add(d)
        u = math.ulp(t)
        for j in (2, 5, 17, 100, 1000):
            add(t + j * u)
            add(t - j * u)


# Inputs on which a one-ulp change of a polynomial tail coefficient of the
# kernel (S1, C1 and T1 in trig_kernel_table.h, in either direction) changes
# the result of sin, cos or tan respectively.  Such a change moves the value by
# about 2^-75 of the result, so a random input shows it with probability about
# 2^-22; these were found by searching 8e7 random arguments in [0, 2^-4]
# against the committed kernel (story 3a, scratch search; the corpus does not
# depend on the kernel, only on these bit patterns).  They are in the corpus so
# that the committed hash sees such a change: check-planted plants each one.
# Coefficients S2, S3, C2, C3 and T2 .. T6 move a result with probability below
# 2^-36 and have no witness; tools/check-planted.py says so.
KERNEL_WITNESSES = (
    0x3fa8177328d74efc,  # S1 down one ulp
    0x3fa173f1421eb6d9,  # S1 down one ulp
    0x3fad6a7f3b6c56e2,  # S1 down one ulp
    0x3fabd80469dd093f,  # S1 up one ulp
    0x3fac4f4f9d50546b,  # S1 up one ulp
    0x3fadd8a144cf5ac7,  # S1 up one ulp
    0x3fa5dba950c429a7,  # C1 down one ulp
    0x3fae68a4786a2108,  # C1 down one ulp
    0x3fa51712cd4d9e66,  # C1 down one ulp
    0x3faa68098377bf85,  # C1 up one ulp
    0x3fad26df605d750d,  # C1 up one ulp
    0x3fad56ed36991ab4,  # C1 up one ulp
    0x3fabf7cc2dee8692,  # T1 down one ulp
    0x3fa7d9824798c298,  # T1 down one ulp
    0x3fab17ea33fb9c0a,  # T1 down one ulp
    0x3f96787c8d06d814,  # T1 up one ulp
    0x3fabe2c5dc230706,  # T1 up one ulp
    0x3fa8aade69d4fb73,  # T1 up one ulp
)


def kernel_inputs(rng, PI, add):
    half_pi = PI / 2
    nrows = 0
    for k in range(256):
        e = -4 + k // 64
        a = math.ldexp(1.0 + (k % 64) / 64.0, e)
        if a > 0.7853981633974483:
            break
        nrows += 1
        nxt = math.ldexp(1.0 + ((k % 64) + 1) / 64.0, e)
        pts = [a, math.nextafter(nxt, 0)]
        for _ in range(2):
            pts.append(a + (nxt - a) * (rng.getrandbits(52) / (1 << 52)))
        for h in pts:
            if h > 0.7853981633974483:
                continue
            add(h)
            add(float(half_pi + Fraction(h)))  # reduced to h again, with an odd quadrant
    assert nrows == 229
    # the direct/table boundary
    d = 2.0 ** -4
    lo = hi = d
    for _ in range(8):
        lo = math.nextafter(lo, 0)
        hi = math.nextafter(hi, 1)
        for h in (lo, hi):
            add(h)
            add(float(half_pi + Fraction(h)))
    add(d)
    add(float(half_pi + Fraction(d)))
    # the direct path's odd quadrant: cot of a remainder at every binade
    for e in range(-28, -4):
        for _ in range(3):
            h = math.ldexp(1.0 + rng.getrandbits(52) / (1 << 52), e)
            add(float(half_pi + Fraction(h)))
            add(float(half_pi - Fraction(h)))
            add(float(3 * half_pi + Fraction(h)))
    for w in KERNEL_WITNESSES:
        add(double_of(w))


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
    # the kernel's table rows and tails, after that
    kernel_inputs(rng, PI, add)
    # the wide fast reduction's edges, after everything else for the same reason
    cw2_inputs(rng, PI, add, n_cw_k, inv)
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
