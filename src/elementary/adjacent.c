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
 * Adjacent IEEE binary64/binary32 values, from integer ordering.
 * See WG14 N1570 7.12.11.3/F.10.8.3 and documentation/design.md.
 */
#include "elem_common.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/macros.h>

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                        FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                        FLT_MAX_EXP == 128,
                    "Float adjacency requires IEEE binary32");

static inline uint64_t adjacent_bits(uint64_t x, uint64_t y, uint64_t sign,
                                     uint64_t infinity, uint64_t quiet,
                                     uint64_t minimum_normal) {
  /* Actual callers have no bits above sign. This explicit width mask also
   * lets binary32 use ordinary 32-bit magnitude operations. */
  uint64_t ax = x & (sign - 1), ay = y & (sign - 1);
  if (ax > infinity || ay > infinity) {
    if ((ax > infinity && !(x & quiet)) || (ay > infinity && !(y & quiet))) {
      (void)gmath_invalid();
    }
    return infinity | quiet;
  }
  if (x == y || (ax == 0 && ay == 0)) {
    return y;
  }
  if (ax == 0) {
    (void)gmath_underflow(0);
    return (y & sign) | UINT64_C(1);
  }
  /* Opposite signs point inward. Same signs point outward only when the
   * destination magnitude is larger. Evaluate both integer Booleans without
   * unpredictable direction branches. After dispatch x is nonzero; outward
   * is 0/1 and can increment only a finite magnitude, so neither operation
   * below wraps. */
  uint64_t outward = (uint64_t)(((x ^ y) & sign) == 0);
  outward &= (uint64_t)(ax < ay);
  x = (x - UINT64_C(1)) + (outward << 1);
  uint64_t result_magnitude = x & (sign - 1);
  if (result_magnitude == infinity && ax < infinity) {
    (void)gmath_overflow(0);
  } else if (result_magnitude < minimum_normal) {
    /* Annex F requires UF/IX even for exact neighboring subnormal values. */
    (void)gmath_underflow(0);
  }
  return x;
}

double gmath_nextafter(double x, double y) {
  return gmath_double(adjacent_bits(
      gmath_bits(x), gmath_bits(y), GMATH_SIGN_BIT, GMATH_INF_BITS,
      UINT64_C(0x0008000000000000), UINT64_C(0x0010000000000000)));
}
float gmath_nextafterf(float x, float y) {
  uint32_t bx, by;
  memcpy(&bx, &x, sizeof bx);
  memcpy(&by, &y, sizeof by);
  uint32_t result = (uint32_t)adjacent_bits(
      bx, by, UINT64_C(0x80000000), UINT64_C(0x7f800000), UINT64_C(0x00400000),
      UINT64_C(0x00800000));
  float output;
  memcpy(&output, &result, sizeof output);
  return output;
}
