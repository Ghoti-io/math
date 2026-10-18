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
 * gmath_scalbn, gmath_ldexp, gmath_frexp and gmath_ilogb: the exponent of a
 * double read and written as an integer, with no floating-point operation on the
 * path of a normal result.  The result of scalbn is exact unless it overflows
 * or is subnormal; a subnormal result is rounded once, to nearest, ties to even,
 * on the integer significand (so there is no double rounding), as IEEE 754
 * scaleB does.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/basic.h>

#include "elem_common.h"

#include <limits.h>

#define GMATH_MANT_MASK 0x000fffffffffffffull
#define GMATH_HIDDEN_BIT 0x0010000000000000ull

/* x of finite nonzero magnitude a: its biased exponent, as if it were normal (zero or negative for a
 * subnormal), and its 52 stored bits with the hidden bit not yet in. */
static inline void gmath_unpack(double x, uint64_t a, int64_t * ex, uint64_t * mant) {
  if (a < GMATH_HIDDEN_BIT) {
    /* subnormal: 2^54 x is exact and normal */
    uint64_t s = gmath_bits(x * 0x1p54) & GMATH_ABS_MASK;
    *ex = (int64_t)(s >> 52) - 54;
    *mant = s & GMATH_MANT_MASK;
  } else {
    *ex = (int64_t)(a >> 52);
    *mant = a & GMATH_MANT_MASK;
  }
}

double gmath_scalbn(double x, int n) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  uint64_t sign = b & GMATH_SIGN_BIT;
  if (a >= GMATH_INF_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  if (a == 0) {
    return x;
  }
  int64_t ex;
  uint64_t mant;
  gmath_unpack(x, a, &ex, &mant);
  /* no double has an exponent range of 5000: a larger n overflows or underflows alike */
  int64_t k = n > 5000 ? 5000 : (n < -5000 ? -5000 : (int64_t)n);
  int64_t ne = ex + k;
  if (ne >= 2047) {
    return gmath_overflow(sign);
  }
  if (ne >= 1) {
    return gmath_double(sign | ((uint64_t)ne << 52) | mant);
  }
  /* subnormal, or zero: the 53-bit significand shifted right by s, rounded to nearest even */
  uint64_t sig = mant | GMATH_HIDDEN_BIT;
  int64_t s = 1 - ne;
  if (s > 54) {
    (void)gmath_underflow(sign);
    return gmath_double(sign);
  }
  uint64_t q = sig >> s;
  uint64_t rem = sig & ((1ull << s) - 1u);
  uint64_t half = 1ull << (s - 1);
  if (rem > half || (rem == half && (q & 1u))) {
    q++;
  }
  if (rem != 0) {
    (void)gmath_underflow(sign); /* tiny and inexact */
  }
  return gmath_double(sign | q);
}

double gmath_ldexp(double x, int n) {
  return gmath_scalbn(x, n);
}

double gmath_frexp(double x, int * e) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  int dummy;
  if (e == NULL) {
    e = &dummy;
  }
  *e = 0;
  if (a >= GMATH_INF_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  if (a == 0) {
    return x;
  }
  int64_t ex;
  uint64_t mant;
  gmath_unpack(x, a, &ex, &mant);
  *e = (int)(ex - 1022);
  return gmath_double((b & GMATH_SIGN_BIT) | ((uint64_t)1022 << 52) | mant);
}

int gmath_ilogb(double x) {
  uint64_t a = gmath_bits(x) & GMATH_ABS_MASK;
  if (a >= GMATH_INF_BITS) {
    (void)gmath_invalid();
    return a > GMATH_INF_BITS ? GMATH_ILOGBNAN : INT_MAX;
  }
  if (a == 0) {
    (void)gmath_invalid();
    return GMATH_ILOGB0;
  }
  int64_t ex;
  uint64_t mant;
  gmath_unpack(x, a, &ex, &mant);
  return (int)(ex - 1023);
}
