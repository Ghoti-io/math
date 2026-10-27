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
 * Minimum and maximum from the ordering of IEEE binary encodings, derived
 * directly from sign-magnitude representation. Positive encodings increase
 * with value; negative encodings decrease. Complement negative magnitudes
 * and set a leading bit on positive ones to obtain unsigned ordered keys.
 * This orders -0 below +0 and avoids floating comparisons on subnormals.
 */
#include <ghoti.io/math/basic.h>

#include <float.h>

#include "elem_common.h"

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
        FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
    "float extrema require IEEE binary32");

static inline uint64_t extrema_bits(uint64_t x, uint64_t y, uint64_t sign,
    uint64_t inf, uint64_t quiet, uint64_t canonical, int maximum) {
  uint64_t magnitude = sign - 1;
  int nx = (x & magnitude) > inf;
  int ny = (y & magnitude) > inf;
  if (nx || ny) {
    if ((nx && (x & quiet) == 0) || (ny && (y & quiet) == 0)) {
      (void)gmath_invalid();
      return canonical;
    }
    if (nx && ny) {
      return canonical;
    }
    return nx ? y : x;
  }
  /* Select with masks: random argument signs must not introduce branches. */
  uint64_t sx = (uint64_t)0 - (uint64_t)((x & sign) != 0);
  uint64_t sy = (uint64_t)0 - (uint64_t)((y & sign) != 0);
  uint64_t kx = x ^ (sign | (sx & magnitude));
  uint64_t ky = y ^ (sign | (sy & magnitude));
  uint64_t choose = (uint64_t)0 - (uint64_t)(maximum ? kx > ky : kx < ky);
  return y ^ ((x ^ y) & choose);
}

double gmath_fmin(double x, double y) {
  return gmath_double(extrema_bits(gmath_bits(x), gmath_bits(y), GMATH_SIGN_BIT,
      GMATH_INF_BITS, 0x0008000000000000ull, GMATH_QNAN_BITS, 0));
}

double gmath_fmax(double x, double y) {
  return gmath_double(extrema_bits(gmath_bits(x), gmath_bits(y), GMATH_SIGN_BIT,
      GMATH_INF_BITS, 0x0008000000000000ull, GMATH_QNAN_BITS, 1));
}

static inline float extrema_float(float x, float y, int maximum) {
  uint32_t xb, yb;
  memcpy(&xb, &x, sizeof xb);
  memcpy(&yb, &y, sizeof yb);
  uint32_t bits = (uint32_t)extrema_bits(
      xb, yb, 0x80000000u, 0x7f800000u, 0x00400000u, 0x7fc00000u, maximum);
  float result;
  memcpy(&result, &bits, sizeof result);
  return result;
}

float gmath_fminf(float x, float y) {
  return extrema_float(x, y, 0);
}

float gmath_fmaxf(float x, float y) {
  return extrema_float(x, y, 1);
}
