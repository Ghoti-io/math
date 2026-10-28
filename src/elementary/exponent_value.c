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
 * @file Floating-valued binary exponents, from raw integer fields.
 * Derived from IEEE representation; N1570 7.12.6.11/F.10.3.11.
 */
#include "elem_common.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/macros.h>
#include <limits.h>

GMATH_STATIC_ASSERT(sizeof(float) == 4 && FLT_RADIX == 2 &&
                        FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                        FLT_MAX_EXP == 128,
                    "Exponent values require IEEE binary32");
GMATH_STATIC_ASSERT(sizeof(double) == 8 && DBL_MANT_DIG == 53 &&
                        DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
                    "Exponent values require IEEE binary64");

/* Call only for a nonzero subnormal significand. */
static inline unsigned lb_top(uint64_t word) {
#if (defined(__GNUC__) || defined(__clang__)) && ULLONG_MAX == UINT64_MAX &&   \
    !defined(GMATH_LOGB_PORTABLE_BITS)
  return 63u - (unsigned)__builtin_clzll((unsigned long long)word);
#else
  unsigned top = 0;
  while (word >> 1) {
    word >>= 1;
    ++top;
  }
  return top;
#endif
}
static inline float lb_float(uint32_t word) {
  float result;
  memcpy(&result, &word, sizeof result);
  return result;
}

double gmath_logb(double x) {
  uint64_t word = gmath_bits(x), a = word & GMATH_ABS_MASK;
  if (a >= GMATH_INF_BITS) {
    if (a == GMATH_INF_BITS) {
      return gmath_double(GMATH_INF_BITS);
    }
    if (!(word & UINT64_C(0x0008000000000000))) {
      (void)gmath_invalid();
    }
    return gmath_double(GMATH_QNAN_BITS);
  }
  if (!a) {
    return gmath_div_by_zero(GMATH_SIGN_BIT);
  }
  int exponent = a < UINT64_C(0x0010000000000000) ? (int)lb_top(a) - 1074
                                                  : (int)(a >> 52) - 1023;
  /* Nonzero integers are exact. Some software integer conversions produce
   * -0 under downward rounding, so construct exponent zero explicitly. */
  return exponent ? (double)exponent : gmath_double(0);
}
float gmath_logbf(float x) {
  uint32_t word;
  memcpy(&word, &x, sizeof word);
  uint32_t a = word & UINT32_C(0x7fffffff);
  if (a >= UINT32_C(0x7f800000)) {
    if (a == UINT32_C(0x7f800000)) {
      return lb_float(UINT32_C(0x7f800000));
    }
    if (!(word & UINT32_C(0x00400000))) {
      (void)gmath_invalid();
    }
    return lb_float(UINT32_C(0x7fc00000));
  }
  if (!a) {
    (void)gmath_div_by_zero(0);
    return lb_float(UINT32_C(0xff800000));
  }
  if (a < UINT32_C(0x00800000)) {
    return (float)((int)lb_top(a) - 149);
  }
  int exponent = (int)(a >> 23) - 127;
  /* Normal exponents [-126,127] convert exactly in every mode.
   * Nonzero preserves every bit; zero clears either zero sign. Unsigned
   * subtraction is defined: the nonzero mask is UINT32_MAX. */
  float converted = (float)exponent;
  uint32_t bits;
  memcpy(&bits, &converted, sizeof bits);
  uint32_t mask = UINT32_C(0) - (uint32_t)(exponent != 0);
  return lb_float(bits & mask);
}
