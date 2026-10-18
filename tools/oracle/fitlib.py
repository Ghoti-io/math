# SPDX-License-Identifier: LGPL-3.0-only
#
# Copyright (C) 2026 Corey Pennycuff
#
# This file is part of Ghoti.io Math.
#
# Ghoti.io Math is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
"""Helpers shared by fit_explog.py and fit_atan2.py (they run in the pinned
oracle image).  The polynomial fit is Lawson's iteratively reweighted least
squares, a published minimax method, as in fit_kernel.py; the working precision
is 240 bits."""

import sys

from mpmath import mp, mpf, matrix, lu_solve, pi

mp.prec = 240

HEADER = """/*
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
"""


def hexd(v):
    """A double, as a C hexadecimal floating literal."""
    return float(v).hex()


def dd(v):
    """v as a double-double (hi, lo)."""
    h = float(v)
    return h, float(v - mpf(h))


def lawson(f, deg, xs, weight, iters=100):
    """Minimax polynomial of degree deg for f on the points xs, minimizing
    weight(x) * |f(x) - p(x)|.  Returns (coefficients low to high, error)."""
    m = len(xs)
    wf = [weight(x) * f(x) for x in xs]
    wp = [[weight(x) * x**j for j in range(deg + 1)] for x in xs]
    lam = [mpf(1) / m] * m
    best = None
    for _ in range(iters):
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


def cheb_points(a, b, m):
    return [(a + b) / 2 - (b - a) / 2 * mp.cos(pi * i / (m - 1)) for i in range(m)]


def measure(f, cd, a, b, weight, n=4001):
    """Worst weighted error of the double-rounded polynomial on a dense grid."""
    w = mpf(0)
    for i in range(0, n):
        x = a + (b - a) * i / (n - 1)
        if x == 0:
            continue
        p = mpf(0)
        for c in reversed(cd):
            p = p * x + mpf(c)
        w = max(w, weight(x) * abs(f(x) - p))
    return w


def fit(name, f, deg, a, b, weight, m=260):
    c, E = lawson(f, deg, cheb_points(a, b, m), weight)
    d = [float(x) for x in c]
    sys.stderr.write("%s, degree %d: minimax 2^%.1f, rounded to double 2^%.1f\n" % (
        name, deg, float(mp.log(E, 2)), float(mp.log(measure(f, d, a, b, weight), 2))))
    return d
