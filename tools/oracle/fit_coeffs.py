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
"""Fit the kernel coefficients of gmath_sin, gmath_cos and gmath_tan and print
src/elementary/trig_tables.h.

Runs in the pinned oracle image (tools/oracle/oracle.py fit).  Everything it
prints is computed here, from mpmath at 400 bits and the Taylor series of sin
and cos; no library's tables or code were read.

What is fitted (Muller, Elementary Functions, chapters 3 and 11; the fit is
Lawson's iteratively reweighted least squares, a published minimax method):

  sin r = r - r^3/6 + r^5 * S(z)         z = r^2, |r| <= pi/4
  cos r = 1 - z/2 + z^2/24 + z^3 * C(z)

The explicit terms are carried in extra precision by the C code (r^3/6 and
z^2/24 as double-doubles, 1 - z/2 by an error-free sum), so only the remainder
is a polynomial in double precision.  S and C are the minimax polynomials, in z on
[0, ZMAX], of

  s(z) = sum_k (-1)^k z^k / (2k+5)!      = (sin r - r + r^3/6) / r^5
  c(z) = sum_k (-1)^(k+1) z^k / (2k+6)!  = (cos r - 1 + z/2 - z^2/24) / z^3

with weight z^2 for s and z^3 for c: an error d(z) in S is an error r^5 d(z) in
sin, which is r^4 d(z) = z^2 d(z) relative to r, and an error z^3 d(z) in cos,
which is about 1.  The fit is a Lawson-weighted minimax fit at 400 bits with the lowest degree
whose worst weighted error is below TARGET; the coefficients are then rounded
to double and the error of the rounded polynomial is measured on a dense grid.

Also printed: the bits of 2/pi as 32-bit words for the Payne-Hanek reduction
(Payne and Hanek, 1983), pi/2 as a double-double, and -1/6 as a double-double.
For the fast reduction of moderate arguments (Cody and Waite, 1980; Muller,
Elementary Functions, chapter 11): 2/pi as a double, and pi/2 split as
P1 + P2 + P3 + P4 with P1..P3 of 33 significant bits each, so that n * Pk is
exact for any n below 2^20, and P4 the double nearest the remainder.
"""

import sys

from mpmath import mp, mpf, matrix, lu_solve, pi

mp.prec = 400

ZMAX = mpf("0.617")  # (pi/4)^2 = 0.61685..., with a margin
ZMIN = mpf("0.002")  # the weight z^2 vanishes at 0; see remez()
TARGET = mpf(2) ** -70
MAXDEG = 14
LIMBS = 42  # 32-bit words of 2/pi: 1344 bits, DBL_MAX needs 38 + 2


def series_s(z):
    t = mpf(1) / 120
    s = mpf(0)
    k = 0
    while True:
        s += t
        k += 1
        t = -t * z / ((2 * k + 4) * (2 * k + 5))
        if abs(t) < mpf(10) ** -110:
            return s + t


def series_c2(z):
    """(cos r - 1 + z/2 - z^2/24) / z^3 = sum_k (-1)^(k+1) z^k / (2k+6)!"""
    t = -mpf(1) / 720
    s = mpf(0)
    k = 0
    while True:
        s += t
        k += 1
        t = -t * z / ((2 * k + 5) * (2 * k + 6))
        if abs(t) < mpf(10) ** -110:
            return s + t


def horner(c, z):
    r = mpf(0)
    for a in reversed(c):
        r = r * z + a
    return r


def minimax(f, deg, a, b, wpow):
    """Near-minimax polynomial of degree deg for f on [a, b], weight x^wpow.

    Lawson's algorithm: a weighted least-squares fit on a grid whose point
    weights are multiplied, each round, by the size of that point's error, so
    the fit converges on the minimax polynomial (the error then equioscillates).
    A plain Remez exchange was tried first and did not converge: the weight
    x^2 makes the error near 0 vanish, and the exchange kept losing one of its
    alternation points to the lobes there.  The grid is Chebyshev-spaced in
    r = sqrt(x), squared, which puts points where the lobes are.  The weight
    vanishes at 0, so the interval starts at ZMIN; below it the weighted error
    is checked by measure(), which starts at 0.
    Returns (coefficients, worst weighted error on the grid)."""
    w = lambda x: x**wpow
    ra, rb = mp.sqrt(a), mp.sqrt(b)
    m = 500
    pts = [((ra + rb) / 2 - (rb - ra) / 2 * mp.cos(pi * i / (m - 1))) ** 2 for i in range(m)]
    wf = [w(x) * f(x) for x in pts]
    wp = [[w(x) * x**j for j in range(deg + 1)] for x in pts]
    lam = [mpf(1) / m] * m
    best = None
    for _ in range(120):
        N = matrix(deg + 1, deg + 1)
        rhs = matrix(deg + 1, 1)
        for i in range(m):
            row = wp[i]
            for j in range(deg + 1):
                rhs[j] += lam[i] * row[j] * wf[i]
                for k in range(j, deg + 1):
                    N[j, k] += lam[i] * row[j] * row[k]
        for j in range(deg + 1):
            for k in range(j):
                N[j, k] = N[k, j]
        sol = lu_solve(N, rhs)
        c = [sol[j] for j in range(deg + 1)]
        errs = [abs(wf[i] - sum(wp[i][j] * c[j] for j in range(deg + 1))) for i in range(m)]
        top = max(errs)
        if best is None or top < best[1]:
            best = (c, top)
        tot = sum(lam[i] * errs[i] for i in range(m))
        lam = [lam[i] * errs[i] / tot for i in range(m)]
    return best


def dd_split(v):
    hi = float(v)
    lo = float(v - mpf(hi))
    return hi, lo


def round_bits(v, bits):
    """v rounded to the nearest number with the given count of significant bits."""
    e = int(mp.floor(mp.log(abs(v), 2)))
    scale = mpf(2) ** (bits - 1 - e)
    return mp.nint(v * scale) / scale


def hexd(d):
    return float(d).hex()


def measure(f, cd, wpow):
    """Worst weighted error of the double-rounded polynomial on a dense grid."""
    worst = mpf(0)
    m = 20000
    for i in range(m + 1):
        z = ZMAX * i / m
        e = abs(z**wpow * (f(z) - horner([mpf(x) for x in cd], z)))
        if e > worst:
            worst = e
    return worst


def fit(name, f, wpow):
    for deg in range(2, MAXDEG + 1):
        try:
            c, E = minimax(f, deg, ZMIN, ZMAX, wpow)
        except ValueError:
            continue
        sys.stderr.write("  %s degree %d: grid error 2^%.2f\n" % (name, deg, float(mp.log(abs(E), 2))))
        if abs(E) < TARGET:
            break
    else:
        raise SystemExit("%s: no degree up to %d reaches 2^-70" % (name, MAXDEG))
    cd = [float(x) for x in c]
    got = measure(f, cd, wpow)
    sys.stderr.write("%s: degree %d, minimax error 2^%.2f, rounded to double 2^%.2f\n" % (
        name, deg, float(mp.log(abs(E), 2)), float(mp.log(got, 2))))
    return cd


def main():
    s_c = fit("S", series_s, 2)
    c_c = fit("C", series_c2, 3)
    limbs = []
    with mp.workprec(32 * LIMBS + 200):
        v = 2 / pi
        for _ in range(LIMBS):
            v *= 2**32
            w = int(mp.floor(v))
            limbs.append(w)
            v -= w
    pio2 = pi / 2
    p_hi, p_lo = dd_split(pio2)
    q_hi, q_lo = dd_split(mpf(-1) / 6)
    t_hi, t_lo = dd_split(mpf(1) / 24)

    cw = []
    rem = pio2
    for _ in range(3):
        part = round_bits(rem, 33)
        cw.append(part)
        rem -= part
    cw.append(mpf(float(rem)))
    inv2pi = float(2 / pi)

    out = []
    w = out.append
    w("""/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Ghoti.io Math is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Ghoti.io Math is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/*
 * GENERATED by tools/oracle/fit_coeffs.py in the pinned oracle image
 * (`make oracle-fit`).  Do not edit; regenerate.  Regenerating changes the
 * results, and so tests/corpus/trig.hash.
 */

#ifndef GHOTI_IO_GMATH_TRIG_TABLES_H
#define GHOTI_IO_GMATH_TRIG_TABLES_H

#include <ghoti.io/math/macros.h>

#include <stdint.h>
""")
    w("/* 2/pi as a binary fraction, 32 bits per word, most significant first,")
    w(" * after two zero words (bits at and before the binary point), which let the")
    w(" * reduction index the table with a small negative start. */")
    w("#define GMATH_TWO_OVER_PI_WORDS %d" % (LIMBS + 2))
    w("static const uint32_t gmath_two_over_pi[GMATH_TWO_OVER_PI_WORDS] = {")
    w("  0x00000000u, 0x00000000u,")
    for i in range(0, LIMBS, 4):
        w("  " + ", ".join("0x%08xu" % x for x in limbs[i:i + 4]) + ",")
    w("};\n")
    w("/* pi/2 as a double-double: hi + lo, relative error 2^-107. */")
    w("#define GMATH_PIO2_HI %s" % hexd(p_hi))
    w("#define GMATH_PIO2_LO %s\n" % hexd(p_lo))
    w("/* The fast reduction: n = round(x * 2/pi), r = x - n*(P1 + P2 + P3 + P4).")
    w(" * P1..P3 have 33 significant bits and so n * Pk is exact for n < 2^20;")
    w(" * P4 is the double nearest what is left of pi/2.  The four sum to pi/2 with")
    w(" * an error below 2^-156. */")
    w("#define GMATH_CW_INV_PIO2 %s" % hexd(inv2pi))
    for i, part in enumerate(cw):
        w("#define GMATH_CW_P%d %s" % (i + 1, hexd(float(part))))
    w("")
    w("/* -1/6 as a double-double. */")
    w("#define GMATH_M1_6_HI %s" % hexd(q_hi))
    w("#define GMATH_M1_6_LO %s\n" % hexd(q_lo))
    w("/* 1/24 as a double-double. */")
    w("#define GMATH_1_24_HI %s" % hexd(t_hi))
    w("#define GMATH_1_24_LO %s\n" % hexd(t_lo))
    w("/* sin r = r - r^3/6 + r^5 * S(r^2); S has degree %d. */" % (len(s_c) - 1))
    w("#define GMATH_SIN_DEGREE %d" % (len(s_c) - 1))
    w("static const double gmath_sin_coeff[GMATH_SIN_DEGREE + 1] = {")
    for x in s_c:
        w("  %s," % hexd(x))
    w("};\n")
    w("/* cos r = 1 - r^2/2 + r^4/24 + r^6 * C(r^2); C has degree %d. */" % (len(c_c) - 1))
    w("#define GMATH_COS_DEGREE %d" % (len(c_c) - 1))
    w("static const double gmath_cos_coeff[GMATH_COS_DEGREE + 1] = {")
    for x in c_c:
        w("  %s," % hexd(x))
    w("};\n")
    w("#endif /* GHOTI_IO_GMATH_TRIG_TABLES_H */")
    sys.stdout.write("\n".join(out) + "\n")


main()
