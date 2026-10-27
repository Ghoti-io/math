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
 * Exact binary32 rounding and sign operations, and correctly rounded sqrtf.
 * Derived from the positional binary format, without implementation sources.
 * Fraction masks remove the low 23-e bits; integer increments select floor,
 * ceil, ties-away or ties-even. The rounding/sign operations never raise
 * inexact for finite inputs.
 *
 * For sqrtf, exact widening and the existing correctly rounded double square
 * root are safe: a normalized float root midpoint has an odd squared numerator
 * on the 2^-48 grid, while the normalized input has at most 24 significant
 * bits. Its root is more than 2^-50 from a float midpoint, compared with at
 * most 2^-53 error from the double square root. See the design proof.
 */
#include <ghoti.io/math/basic.h>
#include <float.h>
#include "elem_common.h"
#include "sqrt_impl.h"

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                    FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
                    "float basic operations require IEEE binary32");

#define FLOAT_BASIC_SIGN 0x80000000u
#define FLOAT_BASIC_ABS 0x7fffffffu
#define FLOAT_BASIC_INF 0x7f800000u
#define FLOAT_BASIC_NAN 0x7fc00000u
#define FLOAT_BASIC_ONE 0x3f800000u
#define FLOAT_BASIC_HALF 0x3f000000u
#define FLOAT_BASIC_TWO23 0x4b000000u

static inline uint32_t floatbasic_word(float x) {
  uint32_t b;
  memcpy(&b, &x, sizeof b);
  return b;
}

static inline float floatbasic_value(uint32_t b) {
  float x;
  memcpy(&x, &b, sizeof x);
  return x;
}

static inline float floatbasic_nan(float x) {
  volatile float t = x - x;
  (void)t;
  return floatbasic_value(FLOAT_BASIC_NAN);
}

enum floatbasic_mode {
  FLOAT_BASIC_FLOOR,
  FLOAT_BASIC_CEIL,
  FLOAT_BASIC_TRUNC,
  FLOAT_BASIC_ROUND,
  FLOAT_BASIC_RINT
};

static inline float floatbasic_round(float x, enum floatbasic_mode mode) {
  uint32_t b = floatbasic_word(x);
  uint32_t a = b & FLOAT_BASIC_ABS;
  uint32_t sign = b & FLOAT_BASIC_SIGN;
  if (a >= FLOAT_BASIC_TWO23) {
    return a > FLOAT_BASIC_INF ? floatbasic_nan(x) : x;
  }
  if (a < FLOAT_BASIC_ONE) {
    unsigned increment;
    if (mode == FLOAT_BASIC_FLOOR) {
      increment = sign != 0 && a != 0;
    }
    else if (mode == FLOAT_BASIC_CEIL) {
      increment = sign == 0 && a != 0;
    }
    else if (mode == FLOAT_BASIC_ROUND) {
      increment = a >= FLOAT_BASIC_HALF;
    }
    else if (mode == FLOAT_BASIC_RINT) {
      increment = a > FLOAT_BASIC_HALF;
    }
    else {
      increment = 0;
    }
    return floatbasic_value(sign | (increment ? FLOAT_BASIC_ONE : 0));
  }
  unsigned cut = 150u - (a >> 23); /* 1 <= cut <= 23. */
  uint32_t unit = 1u << cut;
  uint32_t mask = unit - 1u;
  uint32_t fraction = a & mask;
  uint32_t base = a & ~mask;
  unsigned increment;
  if (mode == FLOAT_BASIC_FLOOR) {
    increment = sign != 0 && fraction != 0;
  }
  else if (mode == FLOAT_BASIC_CEIL) {
    increment = sign == 0 && fraction != 0;
  }
  else if (mode == FLOAT_BASIC_ROUND) {
    increment = fraction >= (unit >> 1);
  }
  else if (mode == FLOAT_BASIC_RINT) {
    uint32_t half = unit >> 1;
    /* Express halfway selection with bit predicates to support branchless code. */
    increment = (unsigned)(fraction > half) |
        ((unsigned)(fraction == half) & ((base >> cut) & 1u));
  }
  else {
    increment = 0;
  }
  return floatbasic_value(sign | (base + (increment ? unit : 0)));
}

float gmath_floorf(float x) {
  return floatbasic_round(x, FLOAT_BASIC_FLOOR);
}

float gmath_ceilf(float x) {
  return floatbasic_round(x, FLOAT_BASIC_CEIL);
}

float gmath_truncf(float x) {
  return floatbasic_round(x, FLOAT_BASIC_TRUNC);
}

float gmath_roundf(float x) {
  return floatbasic_round(x, FLOAT_BASIC_ROUND);
}

float gmath_rintf(float x) {
  return floatbasic_round(x, FLOAT_BASIC_RINT);
}

float gmath_fabsf(float x) {
  uint32_t a = floatbasic_word(x) & FLOAT_BASIC_ABS;
  return a > FLOAT_BASIC_INF ? floatbasic_nan(x) : floatbasic_value(a);
}

float gmath_copysignf(float x, float y) {
  uint32_t a = floatbasic_word(x) & FLOAT_BASIC_ABS;
  if (a > FLOAT_BASIC_INF) {
    return floatbasic_nan(x);
  }
  return floatbasic_value(a | (floatbasic_word(y) & FLOAT_BASIC_SIGN));
}

float gmath_sqrtf(float x) {
  /* Classify before widening or invoking the double instruction/comparison:
   * some target widened-NaN paths signal even for a quiet float input. */
  if ((floatbasic_word(x) & FLOAT_BASIC_ABS) > FLOAT_BASIC_INF) {
    return floatbasic_nan(x);
  }
  double root = gmath_sqrt_impl((double)x);
  /* Fix the float NaN bits explicitly; conversion need not preserve a NaN's
   * payload/sign on every target even though the double kernel canonicalizes. */
  if ((gmath_bits(root) & GMATH_ABS_MASK) > GMATH_INF_BITS) {
    return floatbasic_value(FLOAT_BASIC_NAN);
  }
  return (float)root;
}
