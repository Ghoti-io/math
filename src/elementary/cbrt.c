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
 * Real cube root, derived from a midpoint binomial seed and Newton's method.
 * No other math implementation's source was used.
 *
 * x = m*2^e, 1<=m<2; e=3q+r, 0<=r<3.  The normalized cube root of
 * a=m*2^r lies in [1,2), and its final scaling by 2^q is exact and normal.
 * A cubic Taylor seed at one of 64 midpoints has relative error below 2^-32.
 * One Newton correction from a compensated cube residual squares that error;
 * the last addition supplies the binary64 rounding. See the design notes.
 */
#include <ghoti.io/math/elementary.h>
#include <float.h>
#include "elem_common.h"
#include "cbrt_table.h"

GMATH_STATIC_ASSERT(sizeof(double) == sizeof(uint64_t) && FLT_RADIX == 2 &&
                    DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
                    "cbrt requires IEEE binary64");
GMATH_STATIC_ASSERT(GMATH_CBRT_TABLE_BITS == 6,
                    "cbrt midpoint grid requires 64 rows");

/* Normalize subnormal significands without floating arithmetic or flags. */
static inline unsigned cbrt_shift(uint64_t m) {
#if (defined(__GNUC__) || defined(__clang__)) && !defined(GMATH_CBRT_PORTABLE_BITS)
  return (unsigned)__builtin_clzll((unsigned long long)m) - 11u;
#else
  unsigned shift = 0;
  while (m < (1ull << 52)) {
    m <<= 1;
    ++shift;
  }
  return shift;
#endif
}

double gmath_cbrt(double x) {
  uint64_t xb = gmath_bits(x);
  uint64_t ax = xb & GMATH_ABS_MASK;
  if (ax >= GMATH_INF_BITS) {
    return ax == GMATH_INF_BITS ? x : gmath_nan_of(x);
  }
  if (ax == 0) {
    return x;
  }
  int e = (int)(ax >> 52) - 1023;
  uint64_t fraction = ax & 0x000fffffffffffffull;
  if (ax < (1ull << 52)) {
    unsigned shift = cbrt_shift(ax);
    fraction = (ax << shift) & 0x000fffffffffffffull;
    e = -1022 - (int)shift;
  }
  int q = e / 3;
  int r = e - 3 * q;
  if (r < 0) {
    r += 3;
    --q;
  }
  uint64_t sign = xb & GMATH_SIGN_BIT;
  if (fraction == 0 && r == 0) {
    return gmath_double(((uint64_t)(q + 1023) << 52) | sign);
  }
  unsigned j = (unsigned)(fraction >> (52 - GMATH_CBRT_TABLE_BITS));
  double m = gmath_double(0x3ff0000000000000ull | fraction);
  double midpoint = 1.0 + (double)(2 * j + 1) * 0x1p-7;
  double s = (m - midpoint) * gmath_cbrt_seed[j][0];
  double polynomial = 1.0 + s * (1.0 / 3.0 + s * (-1.0 / 9.0 + s * (5.0 / 81.0)));
  double y = (gmath_cbrt_seed[j][1] * polynomial) * gmath_cbrt_factor[r];
  double a = gmath_double(((uint64_t)(1023 + r) << 52) | fraction);
  gmath_pair square = gmath_two_sqr(y);
  gmath_pair cube = gmath_two_prod(square.hi, y);
  double cube_low = cube.lo + square.lo * y;
  /* a and cube.hi are close, so their subtraction is exact by Sterbenz. */
  double residual = (a - cube.hi) - cube_low;
  double correction = residual / ((3.0 * y) * y);
  double root = y + correction;
  return gmath_double((gmath_bits(root) + ((uint64_t)(int64_t)q << 52)) | sign);
}
