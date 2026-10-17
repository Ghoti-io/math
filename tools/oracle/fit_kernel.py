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
"""Compute the table and the polynomial tails of the sin/cos/tan kernel and
print src/elementary/trig_kernel_table.h.

Runs in the pinned oracle image (tools/oracle/oracle.py fit-kernel, `make
oracle-fit`).  Everything printed is computed here with mpmath at 220 bits;
no library's tables or code were read.  The method is the table-driven
reduction of a small argument (Tang, "Table-driven implementation of the
sine and cosine functions", and Muller, Elementary Functions, chapters 4
and 5), and the polynomials are fitted by Lawson's iteratively reweighted
least squares, a published minimax method.

The reduced argument r (0 <= r <= pi/4 in magnitude) is split r = a + b where
a is r with all but 6 bits of its mantissa cleared (64 slices per binade for
2^-4 <= r < 2^0) and so 0 <= b < a/64.  Row k of the table holds, for the a of
slice k,

    sin a   as a double-double (hi, lo)
    cos a   as a double-double (hi, lo)
    tan a, cot a            as doubles (hi only)
    d0 = sin_hi - tan_hi * cos_hi,   e0 = cos_hi - cot_hi * sin_hi

where d0 and e0 are the exact (high-precision) residuals of the tan and cot
columns, rounded to double (about 2^-54).  The last row is a = 0
(sin 0, cos 0 = 1, the rest 0), which is the "direct" path used below 2^-4.

The polynomial tails, in z = b^2, on 0 < z <= (2^-4)^2 (the direct path's b
reaches 2^-4):

    sin b = b + b z S(z)      S(z) ~ (sin b - b) / (b z)  = -1/6 + z/120 - ...
    cos b = 1 + z C(z)        C(z) ~ (cos b - 1) / z      = -1/2 + z/24 - ...
    tan b = b + b z T(z)      T(z) ~ (tan b - b) / (b z)  =  1/3 + 2z/15 + ...

S and C have degree 3, T degree 6.  Weight z: an error d(z) in S is an error
b z d(z) in sin b, relative to b it is z d(z).  The fit error before and after
rounding the coefficients to double is written to stderr.
"""

import sys

from mpmath import mp, mpf, matrix, lu_solve, pi, sin, cos, tan

mp.prec = 220

SLICE_BITS = 6
BINADES = 4  # 2^-4 .. 2^-1: a slice table for 2^-4 <= a < 1
DEG_S = 3
DEG_C = 3
DEG_T = 6
BMAX = mpf(2) ** -4  # below this the direct path runs: b = r
ZMAX = BMAX**2 * mpf("1.02")
ZMIN = ZMAX / 200


def series(first, step):
    """Return f(z) = first - first*z/step(1) + ..., each term the previous
    times -z / step(k)."""

    def f(z):
        t = first
        s = mpf(0)
        k = 1
        while abs(t) > mpf(10) ** -70:
            s += t
            k += 1
            t = -t * z / step(k)
        return s

    return f


s_f = series(mpf(-1) / 6, lambda k: (2 * k) * (2 * k + 1))  # -1/6 + z/120 - ...
c_f = series(mpf(-1) / 2, lambda k: (2 * k - 1) * (2 * k))  # -1/2 + z/24 - ...


def t_f(z):
    b = mp.sqrt(z)
    return (tan(b) - b) / (b * z)


def horner(c, z):
    r = mpf(0)
    for a in reversed(c):
        r = r * z + a
    return r


def lawson(f, deg):
    m = 240
    ra, rb = mp.sqrt(ZMIN), mp.sqrt(ZMAX)
    pts = [((ra + rb) / 2 - (rb - ra) / 2 * mp.cos(pi * i / (m - 1))) ** 2 for i in range(m)]
    wf = [x * f(x) for x in pts]
    wp = [[x * x**j for j in range(deg + 1)] for x in pts]
    lam = [mpf(1) / m] * m
    best = None
    for _ in range(80):
        N = matrix(deg + 1, deg + 1)
        rhs = matrix(deg + 1, 1)
        for i in range(m):
            for j in range(deg + 1):
                rhs[j] += lam[i] * wp[i][j] * wf[i]
                for k in range(deg + 1):
                    N[j, k] += lam[i] * wp[i][j] * wp[i][k]
        sol = lu_solve(N, rhs)
        c = [sol[j] for j in range(deg + 1)]
        errs = [abs(wf[i] - sum(wp[i][j] * c[j] for j in range(deg + 1))) for i in range(m)]
        top = max(errs)
        if best is None or top < best[1]:
            best = (c, top)
        tot = sum(lam[i] * errs[i] for i in range(m))
        lam = [lam[i] * errs[i] / tot for i in range(m)]
    return best


def measure(f, cd):
    """Worst weighted error of the double-rounded polynomial on a dense grid."""
    w = mpf(0)
    for i in range(1, 4001):
        z = ZMAX * i / 4000
        w = max(w, abs(z * (f(z) - horner([mpf(x) for x in cd], z))))
    return w


def dd(v):
    h = float(v)
    return h, float(v - mpf(h))


def fit(name, f, deg):
    c, E = lawson(f, deg)
    d = [float(x) for x in c]
    sys.stderr.write("%s tail, degree %d: minimax 2^%.1f, rounded to double 2^%.1f\n" % (
        name, deg, float(mp.log(E, 2)), float(mp.log(measure(f, d), 2))))
    return d


def main():
    sd = fit("sin", s_f, DEG_S)
    cd = fit("cos", c_f, DEG_C)
    td = fit("tan", t_f, DEG_T)
    rows = BINADES << SLICE_BITS
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
 * GENERATED by tools/oracle/fit_kernel.py in the pinned oracle image
 * (`make oracle-fit`).  Do not edit; regenerate.  Regenerating changes the
 * results, and so tests/corpus/trig.hash.  The method is described in the
 * comment above the kernel in trig.c.
 */

#ifndef GHOTI_IO_GMATH_TRIG_KERNEL_TABLE_H
#define GHOTI_IO_GMATH_TRIG_KERNEL_TABLE_H

#include <ghoti.io/math/macros.h>
""")
    w("/* Slices per binade of the reduced argument: 2^%d.  Row k of the table is the a of" % SLICE_BITS)
    w(" * slice k, a = 2^e * (1 + s/2^%d) for k = (e + %d) * 2^%d + s, e = -%d .. -1; the extra" % (SLICE_BITS, BINADES, SLICE_BITS, BINADES))
    w(" * last row is a = 0, the direct path. */")
    w("#define GMATH_TRIG_SLICE_BITS %d" % SLICE_BITS)
    w("#define GMATH_TRIG_ROWS %d" % rows)
    w("#define GMATH_TRIG_ZERO_ROW %d" % rows)
    w("")
    w("/* The columns of a row. */")
    for i, n in enumerate(("SIN_HI", "SIN_LO", "COS_HI", "COS_LO", "TAN_HI", "TAN_D0", "COT_HI", "COT_E0")):
        w("#define GMATH_TRIG_%s %d" % (n, i))
    w("")
    w("/* sin b = b + b z S(z), z = b^2: S has degree %d. */" % DEG_S)
    w("#define GMATH_TRIG_SIN_DEGREE %d" % DEG_S)
    w("static const double gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {%s};" % ", ".join(x.hex() for x in map(float, sd)))
    w("")
    w("/* cos b = 1 + z C(z): C has degree %d. */" % DEG_C)
    w("#define GMATH_TRIG_COS_DEGREE %d" % DEG_C)
    w("static const double gmath_trig_cos_tail[GMATH_TRIG_COS_DEGREE + 1] = {%s};" % ", ".join(x.hex() for x in map(float, cd)))
    w("")
    w("/* tan b = b + b z T(z): T has degree %d. */" % DEG_T)
    w("#define GMATH_TRIG_TAN_DEGREE %d" % DEG_T)
    w("static const double gmath_trig_tan_tail[GMATH_TRIG_TAN_DEGREE + 1] = {%s};" % ", ".join(x.hex() for x in map(float, td)))
    w("")
    w("/* test_trig_kernel.cpp includes trig.c as C++, which spells the alignment differently. */")
    w("#ifdef __cplusplus")
    w("#define GMATH_TRIG_ALIGN64 alignas(64)")
    w("#else")
    w("#define GMATH_TRIG_ALIGN64 _Alignas(64)")
    w("#endif")
    w("")
    w("/* sin a hi, sin a lo, cos a hi, cos a lo, tan a, sin_hi - tan * cos_hi, cot a,")
    w(" * cos_hi - cot * sin_hi.  One row is 64 bytes, a cache line. */")
    w("GMATH_TRIG_ALIGN64 static const double gmath_trig_rows[GMATH_TRIG_ROWS + 1][8] = {")
    for e in range(-BINADES, 0):
        for s in range(1 << SLICE_BITS):
            a = mpf(2) ** e * (1 + mpf(s) / (1 << SLICE_BITS))
            sh, sl = dd(sin(a))
            ch, cl = dd(cos(a))
            th = float(tan(a))
            kh = float(1 / tan(a))
            d0 = float(mpf(sh) - mpf(th) * mpf(ch))
            e0 = float(mpf(ch) - mpf(kh) * mpf(sh))
            k = (e + BINADES) * (1 << SLICE_BITS) + s
            w("  /* %3d */ {%s}," % (k, ", ".join(v.hex() for v in (sh, sl, ch, cl, th, d0, kh, e0))))
    w("  /* %3d */ {0x0.0p+0, 0x0.0p+0, 0x1.0p+0, 0x0.0p+0, 0x0.0p+0, 0x0.0p+0, 0x0.0p+0, 0x0.0p+0}," % rows)
    w("};")
    w("")
    w("#endif /* GHOTI_IO_GMATH_TRIG_KERNEL_TABLE_H */")
    sys.stdout.write("\n".join(out) + "\n")


main()
