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
 * Binary32 trig from bounded Taylor series and an integer wide reduction.
 * The series coefficients are reciprocals of factorials, derived directly;
 * no implementation source or third-party coefficient set was used.
 * All polynomial operations are double with contraction disabled. Only the
 * final result is narrowed to float. See the design bounds and oracle tests.
 */
#include <ghoti.io/math/elementary.h>
#include <float.h>
#include "elem_common.h"
#include "floattrig_reduce.h"

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                    FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
                    "float trig requires IEEE binary32");

#define FLOAT_TRIG_ABS 0x7fffffffu
#define FLOAT_TRIG_INF 0x7f800000u
#define FLOAT_TRIG_NAN 0x7fc00000u
#define FLOAT_TRIG_ONE 0x3f800000u
#define FLOAT_TRIG_FAST_MIN 0x4e800000u /* 2^30: below this the double reducer is cheaper. */
#define FLOAT_TRIG_MIN_NORMAL 0x00800000u

static inline uint32_t floattrig_word(float x) {
  uint32_t word;
  memcpy(&word, &x, sizeof word);
  return word;
}

static inline float floattrig_value(uint32_t word) {
  float x;
  memcpy(&x, &word, sizeof x);
  return x;
}

/* Covers infinity (invalid) as well as quiet/signaling NaNs. No widening can
 * change signaling status or invoke a target's double-NaN conversion path. */
static inline float floattrig_nan(float x) {
  volatile float t = x - x;
  (void)t;
  return floattrig_value(FLOAT_TRIG_NAN);
}

/* |x|<=1. Alternating-series truncation errors are <=|x|^13/13!
 * and <=|x|^14/14!, respectively, before the small double rounding errors. */
static inline double floattrig_sin_small(double x) {
  double z = x * x;
  double p = -1.0 / 6.0 + z * (1.0 / 120.0 + z * (-1.0 / 5040.0 +
      z * (1.0 / 362880.0 + z * (-1.0 / 39916800.0))));
  return x + (x * z) * p;
}

static inline double floattrig_cos_small(double x) {
  double z = x * x;
  double p = -1.0 / 2.0 + z * (1.0 / 24.0 + z * (-1.0 / 720.0 +
      z * (1.0 / 40320.0 + z * (-1.0 / 3628800.0 +
      z * (1.0 / 479001600.0)))));
  return 1.0 + z * p;
}

/* Wide-only estimate. Tiny reduced phases and rounding-cell uncertainty
 * retain the established double result. Small-input expressions stay intact. */
static inline int floattrig_wide(uint32_t word, unsigned operation,
                                 float * result) {
  unsigned q;
  double r;
  if (!floattrig_reduce(word & FLOAT_TRIG_ABS, &q, &r)) {
    return 0;
  }
  double y;
  if (operation == 2u) {
    double s = floattrig_sin_small(r);
    double c = floattrig_cos_small(r);
    y = (q & 1u) ? -c / s : s / c;
  }
  else {
    unsigned cosine = (q & 1u) ^ operation;
    y = cosine ? floattrig_cos_small(r) : floattrig_sin_small(r);
    unsigned negative = ((q + operation) >> 1) & 1u;
    y = gmath_double(gmath_bits(y) ^ ((uint64_t)negative << 63));
  }
  if (operation != 1u) {
    y = gmath_double(gmath_bits(y) ^ ((uint64_t)(word >> 31) << 63));
  }
  return floattrig_accept(y, result);
}

static inline float floattrig_finish(double y) {
  float result = (float)y;
  if ((floattrig_word(result) & FLOAT_TRIG_ABS) < FLOAT_TRIG_MIN_NORMAL) {
    /* Nonzero dyadic inputs have inexact trig values. A tiny rounded result
     * must signal even when the intermediate happens to scale/narrow exactly. */
    (void)gmath_underflow(0);
  }
  return result;
}

float gmath_sinf(float x) {
  uint32_t a = floattrig_word(x) & FLOAT_TRIG_ABS;
  if (a >= FLOAT_TRIG_INF) {
    return floattrig_nan(x);
  }
  if (a < FLOAT_TRIG_MIN_NORMAL) {
    if (a != 0) {
      (void)gmath_underflow(0);
    }
    return x;
  }
  if (a <= FLOAT_TRIG_ONE) {
    double wide = (double)x;
    return floattrig_finish(floattrig_sin_small(wide));
  }
  float fast;
  if (a >= FLOAT_TRIG_FAST_MIN && floattrig_wide(floattrig_word(x), 0u, &fast)) {
    return fast;
  }
  double wide = (double)x;
  double y = gmath_sin(wide);
  return floattrig_finish(y);
}

float gmath_cosf(float x) {
  uint32_t a = floattrig_word(x) & FLOAT_TRIG_ABS;
  if (a >= FLOAT_TRIG_INF) {
    return floattrig_nan(x);
  }
  if (a < FLOAT_TRIG_MIN_NORMAL) {
    return 1.0f;
  }
  if (a <= FLOAT_TRIG_ONE) {
    double wide = (double)x;
    return floattrig_finish(floattrig_cos_small(wide));
  }
  float fast;
  if (a >= FLOAT_TRIG_FAST_MIN && floattrig_wide(floattrig_word(x), 1u, &fast)) {
    return fast;
  }
  double wide = (double)x;
  double y = gmath_cos(wide);
  return floattrig_finish(y);
}

float gmath_tanf(float x) {
  uint32_t a = floattrig_word(x) & FLOAT_TRIG_ABS;
  if (a >= FLOAT_TRIG_INF) {
    return floattrig_nan(x);
  }
  if (a < FLOAT_TRIG_MIN_NORMAL) {
    if (a != 0) {
      (void)gmath_underflow(0);
    }
    return x;
  }
  if (a <= FLOAT_TRIG_ONE) {
    double wide = (double)x;
    return floattrig_finish(floattrig_sin_small(wide) / floattrig_cos_small(wide));
  }
  float fast;
  if (a >= FLOAT_TRIG_FAST_MIN && floattrig_wide(floattrig_word(x), 2u, &fast)) {
    return fast;
  }
  double wide = (double)x;
  double y = gmath_tan(wide);
  return floattrig_finish(y);
}
