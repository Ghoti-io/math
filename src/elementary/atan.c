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

/** @file Binary64 unary arctangent with bounded reuse of the binary kernel. */
#include <ghoti.io/math/elementary.h>
#include "elem_common.h"
#include <float.h>

GMATH_STATIC_ASSERT(sizeof(double) == sizeof(uint64_t) && FLT_RADIX == 2 &&
    DBL_MANT_DIG == 53 && DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
    "atan requires IEEE binary64");

static void atan_inexact(void) {
  volatile double one = 1.0, tiny = 0x1p-54;
  volatile double ignored = one + tiny;
  (void)ignored;
}

double gmath_atan(double x) {
  uint64_t word = gmath_bits(x), magnitude = word & GMATH_ABS_MASK;
  if (magnitude > GMATH_INF_BITS) {
    if (!(word & UINT64_C(0x0008000000000000))) {
      (void)gmath_invalid();
    }
    return gmath_double(UINT64_C(0x7ff8000000000000));
  }
  if (!magnitude) {
    return gmath_double(word);
  }
  if (magnitude < UINT64_C(0x3e10000000000000)) {
    /* |x-atan(x)| < |x|^3/3, safely inside the input's nearest cell. */
    if (magnitude < UINT64_C(0x0010000000000000)) {
      (void)gmath_underflow(0);
    } else {
      atan_inexact();
    }
    return gmath_double(word);
  }
  double result;
  if (magnitude >= UINT64_C(0x4350000000000000)) {
    /* Includes infinity. The nearest pi/2 cell contains this whole tail. */
    result = gmath_double(UINT64_C(0x3ff921fb54442d18) |
        (word & GMATH_SIGN_BIT));
  } else {
    /* Bounded operands avoid incidental tiny-reciprocal underflow. */
    result = gmath_atan2(x, 1.0);
  }
  atan_inexact();
  return result;
}
