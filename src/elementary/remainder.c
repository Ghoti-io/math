/*
 * SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Exact binary remainder derived from positional integer arithmetic. If
 * |x| = mx * 2^(ex-52) and |y| = my * 2^(ey-52), with normalized 53-bit
 * significands, the remainder in units of 2^(ey-52) is
 * (mx * 2^(ex-ey)) mod my. Reduce before each shift so every intermediate
 * fits in uint64_t. Eleven bits is the largest universally safe chunk:
 * a remainder is less than the 53-bit divisor, and 53 + 11 = 64.
 *
 * No floating division, quotient rounding, product overflow or subnormal
 * arithmetic is involved. The result is exact: both operands are multiples
 * of their smaller binary unit, and a nonzero remainder is smaller than y,
 * so its significand fits in 53 bits. This is also why a binary32 remainder
 * computed from exactly widened float operands can be narrowed exactly.
 */

#include <ghoti.io/math/basic.h>

#include <float.h>

#include "elem_common.h"

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
        FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
    "fmodf requires IEEE binary32");

/* Number of shifts needed to put a nonzero m's leading bit at fraction.
 * Compiler bit-count instructions do not touch the floating environment.
 * The loop is the reference fallback for a compiler without the intrinsic. */
static inline unsigned remainder_normalize_shift(
    uint64_t m, unsigned fraction) {
#if (defined(__GNUC__) || defined(__clang__)) &&                               \
    !defined(GMATH_REMAINDER_PORTABLE_BITS)
  return (unsigned)__builtin_clzll((unsigned long long)m) - (63u - fraction);
#else
  unsigned shift = 0;
  while (m < (1ull << fraction)) {
    m <<= 1;
    ++shift;
  }
  return shift;
#endif
}

/* a is a finite, nonzero magnitude. Return its normalized significand. */
static inline uint64_t remainder_significand(
    uint64_t a, unsigned fraction, int bias, int * exponent) {
  unsigned field = (unsigned)(a >> fraction);
  uint64_t hidden = 1ull << fraction;
  uint64_t m = a & (hidden - 1);
  *exponent = field ? (int)field - bias : 1 - bias;
  if (field) {
    return m | hidden;
  }
  unsigned shift = remainder_normalize_shift(m, fraction);
  *exponent -= (int)shift;
  return m << shift;
}

/* ax > ay > 0, both finite. Return the exact positive result's bits.
 * The same integer derivation handles binary32 and binary64; no widening
 * or narrowing arithmetic is needed, even for subnormal floats. */
static inline uint64_t remainder_magnitude(
    uint64_t ax, uint64_t ay, unsigned fraction, int bias) {
  uint64_t hidden = 1ull << fraction;
  if (ax < hidden) {
    return ax % ay; /* Both subnormal, already in the same integer unit. */
  }
  int ex, ey;
  uint64_t mx = remainder_significand(ax, fraction, bias, &ex);
  uint64_t my = remainder_significand(ay, fraction, bias, &ey);
  int gap = ex - ey;
  uint64_t r;
  if (my == hidden) {
    /* A power-of-two divisor: only the low fraction bits can survive. */
    if (gap >= (int)fraction) {
      return 0;
    }
    r = (mx << (unsigned)gap) & (hidden - 1);
  }
  else if (gap == 0) {
    r = mx - my; /* ax > ay and equal exponents imply mx > my. */
  }
  else {
    unsigned chunk = 63u - fraction; /* 11 bits for double, 40 for float. */
    if (gap <= (int)chunk) {
      r = (mx << (unsigned)gap) % my;
    }
    else {
      /* Normalized significands differ by less than a factor of two. */
      r = mx >= my ? mx - my : mx;
      while (gap > 0 && r != 0) {
        unsigned shift = gap > (int)chunk ? chunk : (unsigned)gap;
        r = (r << shift) % my;
        gap -= (int)shift;
      }
    }
  }
  if (r == 0) {
    return 0;
  }
  unsigned shift = remainder_normalize_shift(r, fraction);
  r <<= shift;
  ey -= (int)shift;
  if (ey >= 1 - bias) {
    return ((uint64_t)(ey + bias) << fraction) | (r & (hidden - 1));
  }
  /* Exact subnormal: discarded bits are zero and shift <= fraction. */
  return r >> (unsigned)(1 - bias - ey);
}

double gmath_fmod(double x, double y) {
  uint64_t xb = gmath_bits(x), yb = gmath_bits(y);
  uint64_t ax = xb & GMATH_ABS_MASK, ay = yb & GMATH_ABS_MASK;
  uint64_t sign = xb & GMATH_SIGN_BIT;
  if (ax > GMATH_INF_BITS || ay > GMATH_INF_BITS) {
    /* Inspect both: a quiet NaN must not hide a signaling second argument. */
    if (ax > GMATH_INF_BITS) {
      (void)gmath_nan_of(x);
    }
    if (ay > GMATH_INF_BITS) {
      (void)gmath_nan_of(y);
    }
    return gmath_double(GMATH_QNAN_BITS);
  }
  if (ax == GMATH_INF_BITS || ay == 0) {
    return gmath_invalid();
  }
  if (ax < ay) {
    return x; /* Includes signed zero and a finite dividend modulo infinity. */
  }
  if (ax == ay) {
    return gmath_double(sign);
  }

  return gmath_double(sign | remainder_magnitude(ax, ay, 52, 1023));
}

float gmath_fmodf(float x, float y) {
  uint32_t xb, yb;
  memcpy(&xb, &x, sizeof xb);
  memcpy(&yb, &y, sizeof yb);
  uint32_t ax = xb & 0x7fffffffu, ay = yb & 0x7fffffffu;
  uint32_t bits;
  if (ax > 0x7f800000u || ay > 0x7f800000u) {
    if ((ax > 0x7f800000u && (ax & 0x00400000u) == 0) ||
        (ay > 0x7f800000u && (ay & 0x00400000u) == 0)) {
      (void)gmath_invalid();
    }
    bits = 0x7fc00000u;
  }
  else if (ax == 0x7f800000u || ay == 0) {
    (void)gmath_invalid();
    bits = 0x7fc00000u;
  }
  else if (ax < ay) {
    return x;
  }
  else {
    uint32_t sign = xb & 0x80000000u;
    bits =
        sign | (ax == ay ? 0u : (uint32_t)remainder_magnitude(ax, ay, 23, 127));
  }
  float result;
  memcpy(&result, &bits, sizeof result);
  return result;
}
