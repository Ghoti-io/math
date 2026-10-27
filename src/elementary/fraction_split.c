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
 * @file Exact signed integral/fractional splitting.
 * Derived from binary significand geometry; WG14 N1570 7.12.6.12/F.10.3.12.
 */
#include "elem_common.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/macros.h>

GMATH_STATIC_ASSERT(sizeof(float) == 4 && FLT_RADIX == 2 &&
                        FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                        FLT_MAX_EXP == 128,
                    "Fraction splitting requires IEEE binary32");
GMATH_STATIC_ASSERT(sizeof(double) == 8 && DBL_MANT_DIG == 53 &&
                        DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
                    "Fraction splitting requires IEEE binary64");

double gmath_modf(double x, double * integral) {
  uint64_t word = gmath_bits(x), magnitude = word & GMATH_ABS_MASK;
  uint64_t sign = word & GMATH_SIGN_BIT;
  double whole, fraction;
  if (magnitude > GMATH_INF_BITS) {
    if (!(word & UINT64_C(0x0008000000000000))) {
      (void)gmath_invalid();
    }
    whole = fraction = gmath_double(GMATH_QNAN_BITS);
  } else if (magnitude < UINT64_C(0x3ff0000000000000)) {
    whole = gmath_double(sign);
    fraction = x;
  } else if (magnitude >= UINT64_C(0x4330000000000000)) {
    whole = x; /* Includes infinity; no subtraction on this branch. */
    fraction = gmath_double(sign);
  } else {
    unsigned shift = 1075u - (unsigned)(magnitude >> 52); /* 1..52 */
    uint64_t mask = (UINT64_C(1) << shift) - 1;
    whole = gmath_double(word & ~mask);
    /* Whole and x have the same sign, with 1 <= |whole| <= |x| < 2|whole|.
     * Sterbenz makes nonzero subtraction exact in every mode. Its magnitude
     * is >=2^-52, so no underflow is possible. Explicit zero keeps x's sign. */
    fraction = (word & mask) ? x - whole : gmath_double(sign);
  }
  if (integral) {
    *integral = whole;
  }
  return fraction;
}

float gmath_modff(float x, float * integral) {
  uint32_t word;
  memcpy(&word, &x, sizeof word);
  uint32_t magnitude = word & UINT32_C(0x7fffffff);
  uint32_t sign = word & UINT32_C(0x80000000);
  uint32_t whole_word, fraction_word;
  float whole, fraction;
  if (magnitude > UINT32_C(0x7f800000)) {
    if (!(word & UINT32_C(0x00400000))) {
      (void)gmath_invalid();
    }
    whole_word = fraction_word = UINT32_C(0x7fc00000);
  } else if (magnitude < UINT32_C(0x3f800000)) {
    whole_word = sign;
    fraction_word = word;
  } else if (magnitude >= UINT32_C(0x4b000000)) {
    whole_word = word;
    fraction_word = sign;
  } else {
    unsigned shift = 150u - (magnitude >> 23); /* 1..23 */
    uint32_t mask = (UINT32_C(1) << shift) - 1;
    whole_word = word & ~mask;
    memcpy(&whole, &whole_word, sizeof whole);
    /* Same Sterbenz argument as binary64; nonzero fraction >=2^-23. */
    fraction = (word & mask) ? x - whole : 0.0f;
    memcpy(&fraction_word, &fraction, sizeof fraction_word);
    fraction_word |= sign;
  }
  memcpy(&whole, &whole_word, sizeof whole);
  memcpy(&fraction, &fraction_word, sizeof fraction);
  if (integral) {
    *integral = whole;
  }
  return fraction;
}
