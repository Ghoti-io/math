/*
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

/**
 * @file
 *
 * gmath_hypot.
 *
 * Written from the published algorithms, not from any library's source:
 * error-free squares by splitting the operands (Dekker, 1971; Muller,
 * Elementary Functions, chapter 4), the reciprocal square root by Newton's
 * iteration from a tabulated start (Muller, chapter 5), and the square root of
 * a sum by one correction from the exact residual (Markstein's idea, Muller
 * chapter 5, without a fused multiply-add).  The square root is computed here,
 * with + - * / only: the library does not depend on the host for it.
 *
 * With a >= b > 0 scaled by a power of two (exact) to where the squares are
 * normal, and a^2 + b^2 = S exactly as a sum of exact products:
 *
 *   a = ah + al              ah of 26 bits, al of at most 27: ah^2, ah al,
 *                            bh^2 and bh bl are exact, al^2 is below 2^-52 S
 *                            (its rounding does not matter)
 *   s1 + lower = S           s1 the rounded sum of the two leading squares,
 *                            lower the rest to 2^-78 S
 *   sf = s1 + lower          S to 2^-53
 *   r ~ 1/sqrt(sf)           a table start (within 2^-10), then two Newton
 *                            steps: relative error 2^-38
 *   s0 = sf r                sqrt(S) to 2^-37
 *   c  = s0 with 26 bits     so that c^2 is one exact product
 *   R  = (s1 - c^2) + lower  S - c^2, a quantity of 2^-25 S, the sum exact up
 *                            to a rounding of 2^-78 S
 *   h  = c + R / (c + s0)    sqrt(c^2 + R) = c + R / (c + sqrt(c^2 + R))
 *                            exactly; the denominator's error 2^-37 changes h
 *                            by 2^-62 h at most
 *
 * so h is the square root to better than 2^-60, and the final addition is the
 * one rounding: the result is within 0.5 ulp plus 2^-60 of the true value
 * (measured at most 0.5000x over the corpus).  A result that is subnormal is
 * rounded twice, once to 53 bits and once on the scaling back: at most 0.75
 * ulp (measured 0.74).
 *
 * When b < 2^-27 a, hypot is a to within 2^-55 (a quarter of an ulp), and a is
 * returned.  C99 Annex F.9.4.3: hypot(+-inf, y) is +inf even for a NaN y; any
 * other NaN gives the quiet NaN 0x7ff8000000000000; hypot(+-0, +-0) is +0.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/elementary.h>

#include "elem_common.h"
#include "hypot_table.h"

/* An a above 2^300 or below 2^-300 is scaled by 2^-600 or 2^600 so that its square and the
 * squares' error terms are normal, and the result is scaled back (the one place an overflow or
 * an underflow can happen is that last multiplication, which is where one belongs).  The limit
 * is a margin, not a boundary a result can tell. */
#define GMATH_HYPOT_LIMIT 0x1p300

/* The low 27 stored bits cleared leave 26 significant bits. */
#define GMATH_HYPOT_LOW27 0x7ffffffull

double gmath_hypot(double x, double y) {
  uint64_t xb = gmath_bits(x) & GMATH_ABS_MASK;
  uint64_t yb = gmath_bits(y) & GMATH_ABS_MASK;
  if (xb >= GMATH_INF_BITS || yb >= GMATH_INF_BITS) {
    if (xb == GMATH_INF_BITS || yb == GMATH_INF_BITS) {
      return gmath_double(GMATH_INF_BITS);
    }
    return gmath_nan_of(xb > GMATH_INF_BITS ? x : y);
  }
  uint64_t abits = xb > yb ? xb : yb;
  uint64_t bbits = xb > yb ? yb : xb;
  double a = gmath_double(abits);
  double b = gmath_double(bbits);
  /* b/a below 2^-27: exponent difference of 28 or more */
  if (abits - bbits >= ((uint64_t)28 << 52) || bbits == 0) {
    return a;
  }
  double unscale = 1.0;
  if (abits - gmath_bits(1 / GMATH_HYPOT_LIMIT) > gmath_bits(GMATH_HYPOT_LIMIT) - gmath_bits(1 / GMATH_HYPOT_LIMIT)) {
    /* a above 2^300 or below 2^-300 */
    double scale = abits > gmath_bits(GMATH_HYPOT_LIMIT) ? 0x1p-600 : 0x1p600;
    unscale = 1 / scale;
    a *= scale;
    b *= scale;
  }

  /* a = ah + al, ah of 26 bits, al of at most 27: ah^2, ah al and bh^2, bh bl are exact products,
   * and al^2 is below 2^-52 a^2, so its rounding does not matter. */
  double ah = gmath_double(gmath_bits(a) & ~GMATH_HYPOT_LOW27);
  double bh = gmath_double(gmath_bits(b) & ~GMATH_HYPOT_LOW27);
  double al = a - ah;
  double bl = b - bh;
  gmath_pair lead = gmath_fast_two_sum(ah * ah, bh * bh); /* ah >= bh */
  double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl)) + lead.lo;
  double s1 = lead.hi;
  double sf = s1 + lower;

  /* 1/sqrt(sf): the table start (within 2^-10), then two Newton steps (2^-19.4, 2^-38.2).  sf =
   * 2^(2 half + q) (1 + f); the row holds 1/sqrt(2^q (1 + f)) for the leading bits of f. */
  uint64_t sb = gmath_bits(sf);
  int64_t half = ((int64_t)(sb >> 52) - 1023) >> 1;
  double hs = 0.5 * sf;
  double r = gmath_double(gmath_bits(gmath_hypot_rsqrt[(sb >> 44) & ((1u << GMATH_HYPOT_ROW_BITS) - 1u)]) -
      ((uint64_t)half << 52));
  r = r * (1.5 - hs * (r * r));
  r = r * (1.5 - hs * (r * r));
  double s0 = sf * r;
  double c = gmath_double(gmath_bits(s0) & ~GMATH_HYPOT_LOW27);
  double resid = (s1 - c * c) + lower;
  double h = c + resid / (c + s0);
  return unscale == 1.0 ? h : h * unscale;
}
