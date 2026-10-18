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
"""Compute the tables and polynomials of gmath_exp, gmath_log and gmath_pow and
print src/elementary/explog_tables.h.

Runs in the pinned oracle image (tools/oracle/oracle.py fit-explog, `make
oracle-fit`).  Everything printed is computed here with mpmath at 240 bits; no
library's tables or code were read.  The methods are Tang's table-driven exp
and log (Tang, "Table-driven implementation of the exponential function in
IEEE floating-point arithmetic", 1989, and "... of the logarithm function",
1990; Muller, Elementary Functions, chapters 4 to 6), and the polynomials are
fitted by Lawson's iteratively reweighted least squares, a published minimax
method.

exp.  x = (128 k + j) ln2 / 128 + r, |r| <= ln2/256, exp x = 2^k 2^(j/128)
exp(r).  Table: 2^(j/128) as a double-double.  The reduction constants are
ln2/128 as L1 (30 bits, so that n L1 is exact for |n| < 2^23) and L2 =
ln2/128 - L1.  exp r = 1 + r + r^2 P(r), P of degree 3.

log.  x = 2^e m with m in [OFFV, 2 OFFV), OFFV = 0.70703125 (the bit pattern
GMATH_LOG_OFF), cut into 128 rows by the top seven bits of m's offset bit
pattern: 75 rows below 1 (width 2^-8) and 53 from 1 up (width 2^-7).  Row j
has a short multiplier c_j (26 bits, about 1/mid) so that z = m c_j - 1 is
computed exactly in two parts, and t_j = -log c_j as a double-double with
T_HI a multiple of 2^-41.  The two rows that touch 1.0 have c = 1 and t = 0, so
that log x for x near 1 is log1p(z) with z = x - 1 exact and no cancellation.
log m = t_j + log1p(z), log1p z = z + z^2 P(z), P of degree 5 fitted to be
accurate relative to z; pow uses the longer log1p z = z - z^2/2 + z^3 R(z), R of
degree 6.
"""

import sys

from fitlib import HEADER, dd, fit, hexd, mp, mpf
from mpmath import exp, log

sys.stderr.write("fit_explog.py, mpmath at %d bits\n" % mp.prec)

LN2 = log(mpf(2))
N_EXP = 128
LOG_ROWS = 128
OFF = 0x3FE6A00000000000  # bits of OFFV; 1.0 is on a row boundary
LN2_BITS = 41


def trunc_bits(v, bits):
    """v with all but the leading `bits` significant bits cleared (toward zero)."""
    e = int(mp.floor(mp.log(abs(v), 2)))
    q = mpf(2) ** (e - bits + 1)
    return mp.floor(abs(v) / q) * q * (1 if v > 0 else -1)


def round_bits(v, bits):
    e = int(mp.floor(mp.log(abs(v), 2)))
    q = mpf(2) ** (e - bits + 1)
    return mp.nint(v / q) * q


def bits_value(b):
    import struct
    return mpf(struct.unpack(">d", struct.pack(">Q", b))[0])


def main():
    # ---- ln2 split, exp reduction constants ----
    ln2_hi = trunc_bits(LN2, LN2_BITS)
    ln2_lo = float(LN2 - ln2_hi)
    l1 = trunc_bits(LN2 / N_EXP, 30)
    l2 = float(LN2 / N_EXP - l1)
    inv = float(N_EXP / LN2)

    R = LN2 / (2 * N_EXP) * mpf("1.002")

    def g(r):
        return (exp(r) - 1 - r) / (r * r)

    expc = fit("exp: (exp r - 1 - r)/r^2", g, 3, -R, R, lambda r: r * r, m=120)

    # ---- thresholds ----
    two1024 = mpf(2) ** 1024
    over = two1024 - mpf(2) ** 970  # halfway between DBL_MAX and 2^1024
    x = float(log(over))
    import math
    while exp(mpf(x)) >= over:
        x = math.nextafter(x, 0.0)
    while exp(mpf(math.nextafter(x, 1e300))) < over:
        x = math.nextafter(x, 1e300)
    x_over = x
    under = mpf(2) ** -1075  # halfway between 0 and the least subnormal
    x = float(log(under))
    while exp(mpf(x)) <= under:
        x = math.nextafter(x, 1e300)
    while exp(mpf(math.nextafter(x, -1e300))) > under:
        x = math.nextafter(x, -1e300)
    x_under = x
    sys.stderr.write("exp overflows above %r, underflows to zero below %r\n" % (x_over, x_under))

    # ---- log rows ----
    rows = []
    zmax = mpf(0)
    zmin = mpf(0)
    tmin = mpf(10)
    zgen = mpf(0)
    for j in range(LOG_ROWS):
        lo = bits_value(OFF + (j << 45))
        hi = bits_value(OFF + ((j + 1) << 45))
        if lo <= 1 <= hi and (lo == 1 or hi == 1):
            c = mpf(1)
        else:
            c = round_bits(2 / (lo + hi), 26)
        t = -log(c)
        t_hi = round_bits(t, 40) if t != 0 else mpf(0)
        # t_hi must be a multiple of 2^-41
        q = mpf(2) ** -41
        t_hi = mp.nint(t / q) * q
        t_lo = float(t - t_hi)
        zl_ = lo * c - 1
        zh_ = hi * c - 1
        zmax = max(zmax, zh_)
        zmin = min(zmin, zl_)
        if c != 1:
            tmin = min(tmin, abs(t_hi))
            zgen = max(zgen, abs(zh_), abs(zl_))
        rows.append((float(c), float(t_hi), t_lo))
    sys.stderr.write("log rows: z in [%g, %g] (2^%.2f, -2^%.2f); smallest |t_hi| of a row with c != 1: 2^%.2f, largest |z| of those 2^%.2f\n" % (
        float(zmin), float(zmax), float(mp.log(zmax, 2)), float(mp.log(-zmin, 2)), float(mp.log(tmin, 2)), float(mp.log(zgen, 2))))
    assert tmin > zgen * 1.0001, "FastTwoSum(A, z) would be invalid"
    rowsd = [r for r in rows]
    # which rows have c == 1?
    ones = [j for j, r in enumerate(rows) if r[0] == 1.0]
    sys.stderr.write("rows with c = 1: %s\n" % ones)
    assert ones == [74, 75]

    zlo, zhi = -mpf(2) ** -8 * mpf("1.01"), mpf(2) ** -7 * mpf("1.01")

    def p1(z):
        return (log(1 + z) - z) / (z * z)

    def r3(z):
        return (log(1 + z) - z + z * z / 2) / z**3

    logc = fit("log: (log1p z - z)/z^2", p1, 5, zlo, zhi, lambda z: abs(z), m=120)
    powc = fit("pow: (log1p z - z + z^2/2)/z^3", r3, 6, zlo, zhi, lambda z: z * z, m=120)

    out = []
    w = out.append
    w(HEADER)
    w("""/*
 * GENERATED by tools/oracle/fit_explog.py in the pinned oracle image
 * (`make oracle-fit`).  Do not edit; regenerate.  Regenerating changes the
 * results, and so tests/corpus/trig.hash.  The methods are described in the
 * comments above the functions in explog.c.
 */

#ifndef GHOTI_IO_GMATH_EXPLOG_TABLES_H
#define GHOTI_IO_GMATH_EXPLOG_TABLES_H

#include <ghoti.io/math/macros.h>

#include "elem_common.h"
""")
    w("/* ln2 = LN2_HI + LN2_LO, LN2_HI with %d significant bits so that e * LN2_HI is exact. */" % LN2_BITS)
    w("#define GMATH_LN2_HI %s" % hexd(ln2_hi))
    w("#define GMATH_LN2_LO %s" % hexd(ln2_lo))
    w("")
    w("/* exp: n = round(x * 128/ln2), r = x - n L1 - n L2 with n L1 exact. */")
    w("#define GMATH_EXP_TABLE_BITS 7")
    w("#define GMATH_EXP_INV_LN2_N %s" % hexd(inv))
    w("#define GMATH_EXP_L1 %s" % hexd(l1))
    w("#define GMATH_EXP_L2 %s" % hexd(l2))
    w("/* exp r = 1 + r + r^2 (C2 + C3 r + C4 r^2 + C5 r^3), |r| <= ln2/256. */")
    w("#define GMATH_EXP_POLY_DEGREE 3")
    w("static const double gmath_exp_poly[GMATH_EXP_POLY_DEGREE + 1] = {%s};" % ", ".join(hexd(c) for c in expc))
    w("")
    w("/* 2^(j/128) as hi, lo, for j = 0 .. 127. */")
    w("GMATH_ALIGN16 static const double gmath_exp_tab[2 * (1 << GMATH_EXP_TABLE_BITS)] = {")
    for j in range(N_EXP):
        h, l = dd(mpf(2) ** (mpf(j) / N_EXP))
        w("  /* %3d */ %s, %s," % (j, hexd(h), hexd(l)))
    w("};")
    w("")
    w("/* log: the bit pattern whose value is the least m, and the row count. */")
    w("#define GMATH_LOG_OFF 0x%016XULL" % OFF)
    w("#define GMATH_LOG_ROW_BITS 7")
    w("/* The two rows that contain 1.0, with c = 1 and t = 0. */")
    w("#define GMATH_LOG_ONE_ROW_LO 74")
    w("#define GMATH_LOG_ONE_ROW_HI 75")
    w("/* log1p z = z + z^2 (P0 + P1 z + ... + P5 z^5), -2^-8 <= z <= 2^-7. */")
    w("#define GMATH_LOG_POLY_DEGREE 5")
    w("static const double gmath_log_poly[GMATH_LOG_POLY_DEGREE + 1] = {%s};" % ", ".join(hexd(c) for c in logc))
    w("/* log1p z = z - z^2/2 + z^3 (R0 + R1 z + ... + R6 z^6), the same range, for pow. */")
    w("#define GMATH_LOG_DD_DEGREE 6")
    w("static const double gmath_log_dd_poly[GMATH_LOG_DD_DEGREE + 1] = {%s};" % ", ".join(hexd(c) for c in powc))
    w("")
    w("/* c, t_hi, t_lo, 0: row j covers the m whose offset bits have top seven bits j; z = m c - 1, log m = t + log1p z. */")
    w("GMATH_ALIGN16 static const double gmath_log_rows[1 << GMATH_LOG_ROW_BITS][4] = {")
    for j, (c, th, tl) in enumerate(rows):
        w("  /* %3d */ {%s, %s, %s, 0x0.0p+0}," % (j, hexd(c), hexd(th), hexd(tl)))
    w("};")
    w("")
    w("#endif /* GHOTI_IO_GMATH_EXPLOG_TABLES_H */")
    sys.stdout.write("\n".join(out) + "\n")


main()
