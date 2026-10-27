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
 * gmath_hypot.
 *
 * Written from the published algorithms, not from any library's source:
 * error-free squares by splitting the operands (Dekker, 1971; Muller,
 * Elementary Functions, chapter 4) and the square root of a sum by one
 * correction from the exact residual (Markstein's idea, Muller chapter 5,
 * without a fused multiply-add).  The square root it starts from is
 * gmath_sqrt's (sqrt_impl.h: the instruction where the target's rounds
 * correctly, the portable method elsewhere; the same bits either way), not
 * libm's, and not a separate one: story 4 computed it here with + - * / only,
 * and story 4a replaced that by the library's own correctly rounded one.
 *
 * With a >= b > 0 scaled by a power of two (exact) to where the squares are
 * normal, and a^2 + b^2 = S exactly as a sum of exact products:
 *
 *   a = ah + al              ah of 26 bits, al of at most 27: ah^2, ah al,
 *                            bh^2 and bh bl are exact, al^2 is below 2^-52 S
 *                            (its rounding does not matter)
 *   s1 + lower = S           s1 the rounded sum of the two leading squares,
 *                            lower the rest to 2^-78 S
 *   sf = s1 + lower          S to 2^-53
 *   s0 = sqrt(sf)            correctly rounded: sqrt(S) to 2^-53
 *   c  = s0 with 26 bits     so that c^2 is one exact product
 *   R  = (s1 - c^2) + lower  S - c^2, a quantity of 2^-25 S, the sum exact up
 *                            to a rounding of 2^-78 S
 *   h  = c + R / (c + s0)    sqrt(c^2 + R) = c + R / (c + sqrt(c^2 + R))
 *                            exactly; the denominator's error 2^-53 changes h
 *                            by 2^-78 h at most
 *
 * so h is the square root to better than 2^-60 (the rounding of sf, the 2^-78
 * of R and of the product's tails), and the final addition is the one rounding:
 * the result is within 0.5 ulp plus 2^-60 of the true value
 * (measured at most 0.5000x over the corpus).  A result that is subnormal is
 * rounded twice, once to 53 bits and once on the scaling back: at most 0.75
 * ulp (measured 0.74).
 *
 * When b < 2^-27 a, hypot is a to within 2^-55 (a quarter of an ulp), and a is
 * returned.  C99 Annex F.9.4.3: hypot(+-inf, y) is +inf even for a NaN y; any
 * other NaN gives the quiet NaN 0x7ff8000000000000; hypot(+-0, +-0) is +0.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/elementary.h>
#include <float.h>

#include "elem_common.h"
#include "sqrt_impl.h"

/* An a above 2^300 or below 2^-300 is scaled by 2^-600 or 2^600 so that its square and the
 * squares' error terms are normal, and the result is scaled back (the one place an overflow or
 * an underflow can happen is that last multiplication, which is where one belongs).  The limit
 * is a margin, not a boundary a result can tell. */
#define GMATH_HYPOT_LIMIT 0x1p300

/* The low 27 stored bits cleared leave 26 significant bits. */
#define GMATH_HYPOT_LOW27 0x7ffffffull

double gmath_hypot(double x, double y) {
  uint64_t xb = gmath_bits(x) & GMATH_ABS_MASK;
  uint64_t yb = gmath_bits(y) & GMATH_ABS_MASK;
  if (xb >= GMATH_INF_BITS || yb >= GMATH_INF_BITS) {
    if (xb == GMATH_INF_BITS || yb == GMATH_INF_BITS) {
      return gmath_double(GMATH_INF_BITS);
    }
    return gmath_nan_of(xb > GMATH_INF_BITS ? x : y);
  }
  uint64_t abits = xb > yb ? xb : yb;
  uint64_t bbits = xb > yb ? yb : xb;
  double a = gmath_double(abits);
  double b = gmath_double(bbits);
  /* b/a below 2^-27: exponent difference of 28 or more */
  if (abits - bbits >= ((uint64_t)28 << 52) || bbits == 0) {
    return a;
  }
  double unscale = 1.0;
  if (abits - gmath_bits(1 / GMATH_HYPOT_LIMIT) > gmath_bits(GMATH_HYPOT_LIMIT) - gmath_bits(1 / GMATH_HYPOT_LIMIT)) {
    /* a above 2^300 or below 2^-300 */
    double scale = abits > gmath_bits(GMATH_HYPOT_LIMIT) ? 0x1p-600 : 0x1p600;
    unscale = 1 / scale;
    a *= scale;
    b *= scale;
  }

  /* a = ah + al, ah of 26 bits, al of at most 27: ah^2, ah al and bh^2, bh bl are exact products,
   * and al^2 is below 2^-52 a^2, so its rounding does not matter. */
  double ah = gmath_double(gmath_bits(a) & ~GMATH_HYPOT_LOW27);
  double bh = gmath_double(gmath_bits(b) & ~GMATH_HYPOT_LOW27);
  double al = a - ah;
  double bl = b - bh;
  gmath_pair lead = gmath_fast_two_sum(ah * ah, bh * bh); /* ah >= bh */
  double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl)) + lead.lo;
  double s1 = lead.hi;
  double sf = s1 + lower;

  double s0 = gmath_sqrt_impl(sf);
  double c = gmath_double(gmath_bits(s0) & ~GMATH_HYPOT_LOW27);
  double resid = (s1 - c * c) + lower;
  double h = c + resid / (c + s0);
  return unscale == 1.0 ? h : h * unscale;
}

/* Binary32 uses an exact integer sum of squares. At most twelve normalized
 * exponent bits are aligned; larger gaps round to the larger input. */
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                    FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                    FLT_MAX_EXP == 128, "hypotf requires IEEE binary32");

typedef struct {
  uint64_t low;
  uint32_t high;
} hypotf_uint96;

static inline unsigned hf_bitlen(uint64_t hf_word) {
#if defined(__GNUC__) || defined(__clang__)
  return 64u - (unsigned)__builtin_clzll(hf_word); /* Nonzero by construction. */
#else
  unsigned hf_bits = 0;
  do { ++hf_bits; hf_word >>= 1; } while (hf_word != 0);
  return hf_bits;
#endif
}

/* The shifted value has at most 95 bits, and 0<=shift<=46. */
static inline hypotf_uint96 hf_shift(uint64_t hf_word, unsigned hf_shift_bits) {
  hypotf_uint96 hf_result;
  hf_result.low = hf_word << hf_shift_bits;
  hf_result.high = hf_shift_bits == 0 ? 0u :
      (uint32_t)(hf_word >> (64u - hf_shift_bits));
  return hf_result;
}

/* Callers retain at most 50 bits; when shift==0 high is necessarily zero. */
static inline uint64_t hf_right(hypotf_uint96 hf_value, unsigned hf_shift_bits) {
  if (hf_shift_bits == 0) return hf_value.low;
  return (hf_value.low >> hf_shift_bits) |
      ((uint64_t)hf_value.high << (64u - hf_shift_bits));
}

static inline float hf_value(uint32_t hf_word) {
  float hf_result;
  memcpy(&hf_result, &hf_word, sizeof hf_result);
  return hf_result;
}

static inline void hf_inexact(void) {
  volatile double hf_big = 0x1p100;
  volatile double hf_ignored = hf_big + 1.0;
  (void)hf_ignored;
}

static inline void hf_normalize(uint32_t hf_word, uint32_t * hf_mantissa,
                                int * hf_exponent) {
  unsigned hf_field = hf_word >> 23;
  uint32_t hf_m = hf_word & 0x007fffffu;
  if (hf_field != 0) {
    *hf_mantissa = hf_m | 0x00800000u;
    *hf_exponent = (int)hf_field - 150;
  }
  else {
    unsigned hf_shift_bits = 24u - hf_bitlen(hf_m);
    *hf_mantissa = hf_m << hf_shift_bits;
    *hf_exponent = -149 - (int)hf_shift_bits;
  }
}

/* floor(sqrt(T)), 1<=T<2^48. A noninteger root is at least 2^-25 from
 * an integer boundary, versus at most 2^-29 binary64 spacing below 2^24.
 * Thus raw-bit flooring of the instruction is identical in every mode. */
static inline uint32_t hf_isqrt48(uint64_t hf_t) {
#ifdef GMATH_HW_SQRT
  double hf_input = gmath_double(UINT64_C(0x4330000000000000) + hf_t) - 0x1p52;
  double hf_root = gmath_sqrt_instruction(hf_input);
  uint64_t hf_bits = gmath_bits(hf_root);
  unsigned hf_e = (unsigned)(hf_bits >> 52) - 1023u;
  return (uint32_t)(((hf_bits & UINT64_C(0x000fffffffffffff)) |
      (UINT64_C(1) << 52)) >> (52u - hf_e));
#else
  uint64_t hf_root = 0;
  uint64_t hf_remainder = 0;
  for (int hf_digit = 23; hf_digit >= 0; --hf_digit) {
    hf_remainder = (hf_remainder << 2) | ((hf_t >> (2 * hf_digit)) & 3u);
    uint64_t hf_trial = (hf_root << 2) | 1u;
    hf_root <<= 1;
    if (hf_remainder >= hf_trial) {
      hf_remainder -= hf_trial;
      hf_root |= 1u;
    }
  }
  return (uint32_t)hf_root;
#endif
}

#ifdef GMATH_HW_SQRT
/* The exact integer path below decides hard cells. Here the only rounded
 * arithmetic is one positive binary64 sum and its native square root: the
 * relative error is <4*2^-53 in every mode. Reject a 32-double-ULP band
 * around every float midpoint, then round the estimate with integer bits. */
static inline int hf_fast(uint32_t hf_ma, uint32_t hf_mb, int hf_ka, int hf_kb,
                           uint32_t hf_a, uint32_t hf_b, uint32_t * hf_output) {
  double hf_da = gmath_double(((uint64_t)(hf_ka + 1046) << 52) |
      ((uint64_t)(hf_ma & 0x007fffffu) << 29));
  double hf_db = gmath_double(((uint64_t)(hf_kb + 1046) << 52) |
      ((uint64_t)(hf_mb & 0x007fffffu) << 29));
  double hf_sum = hf_da * hf_da + hf_db * hf_db;
  double hf_root = gmath_sqrt_instruction(hf_sum);
  uint64_t hf_bits = gmath_bits(hf_root);
  int hf_e = (int)(hf_bits >> 52) - 1023;
  if (hf_e >= 128) {
    (void)gmath_overflow(0);
    *hf_output = 0x7f800000u;
    return 1;
  }
  unsigned hf_cut = hf_e >= -126 ? 29u : (unsigned)(-97 - hf_e);
  uint64_t hf_sig = (hf_bits & UINT64_C(0x000fffffffffffff)) | (UINT64_C(1) << 52);
  uint64_t hf_mask = (UINT64_C(1) << hf_cut) - 1u;
  uint64_t hf_fraction = hf_sig & hf_mask;
  uint64_t hf_half = UINT64_C(1) << (hf_cut - 1u);
  uint64_t hf_distance = hf_fraction > hf_half ? hf_fraction - hf_half : hf_half - hf_fraction;
  if (hf_distance <= 32u) return 0;
  uint32_t hf_q = (uint32_t)(hf_sig >> hf_cut) + (uint32_t)(hf_fraction > hf_half);
  uint32_t hf_result = hf_e >= -126 ? ((uint32_t)(hf_e + 126) << 23) + hf_q : hf_q;
  if (hf_result >= 0x7f800000u) {
    (void)gmath_overflow(0);
  }
  else if (hf_result < 0x00800000u) {
    /* Both inputs are subnormal here, with the same 2^-149 unit. */
    uint64_t hf_exact_sum = (uint64_t)hf_a * hf_a + (uint64_t)hf_b * hf_b;
    if ((uint64_t)hf_result * hf_result != hf_exact_sum) (void)gmath_underflow(0);
  }
  else if (hf_bits >= gmath_bits(0x1p-126) && hf_bits <= gmath_bits(0x1.fffffep127)) {
    /* An exactly representable Float root makes every preceding operation
     * exact. This narrowing supplies IX for exact-Double/non-Float roots,
     * while its closed normal range excludes any incidental UF or OF. */
    volatile float hf_ignored = (float)hf_root;
    (void)hf_ignored;
  }
  else {
    /* Nearest min-normal/max-finite can straddle the mathematical boundary.
     * Do not narrow under the ambient mode and spuriously force UF/OF. */
    hf_inexact();
  }
  *hf_output = hf_result;
  return 1;
}
#endif

float gmath_hypotf(float x, float y) {
  uint32_t hf_x, hf_y;
  memcpy(&hf_x, &x, sizeof hf_x);
  memcpy(&hf_y, &y, sizeof hf_y);
  hf_x &= 0x7fffffffu;
  hf_y &= 0x7fffffffu;
  /* Signaling NaNs take priority even over infinity. Quiet NaNs do not. */
  if ((hf_x > 0x7f800000u && (hf_x & 0x00400000u) == 0) ||
      (hf_y > 0x7f800000u && (hf_y & 0x00400000u) == 0)) {
    (void)gmath_invalid();
    return hf_value(0x7fc00000u);
  }
  if (hf_x == 0x7f800000u || hf_y == 0x7f800000u) return hf_value(0x7f800000u);
  if (hf_x > 0x7f800000u || hf_y > 0x7f800000u) return hf_value(0x7fc00000u);
  uint32_t hf_a = hf_x > hf_y ? hf_x : hf_y;
  uint32_t hf_b = hf_x > hf_y ? hf_y : hf_x;
  if (hf_b == 0) return hf_value(hf_a);
  uint32_t hf_ma, hf_mb;
  int hf_ka, hf_kb;
  hf_normalize(hf_a, &hf_ma, &hf_ka);
  hf_normalize(hf_b, &hf_mb, &hf_kb);
  unsigned hf_gap = (unsigned)(hf_ka - hf_kb);
  if (hf_gap >= 13u) {
    /* Increment < Mb^2/(2Ma)*2^-26 ULP(a) < 1/4, strictly. */
    if (hf_a < 0x00800000u) (void)gmath_underflow(0);
    else hf_inexact();
    return hf_value(hf_a);
  }
#ifdef GMATH_HW_SQRT
  uint32_t hf_fast_result;
  if (hf_fast(hf_ma, hf_mb, hf_ka, hf_kb, hf_a, hf_b, &hf_fast_result)) {
    return hf_value(hf_fast_result);
  }
#endif
  uint64_t hf_aa = (uint64_t)hf_ma * hf_ma;
  uint64_t hf_bb = (uint64_t)hf_mb * hf_mb;
  hypotf_uint96 hf_s = hf_shift(hf_aa, 2u * hf_gap);
  uint64_t hf_before = hf_s.low;
  hf_s.low += hf_bb;
  hf_s.high += (uint32_t)(hf_s.low < hf_before);
  unsigned hf_length = hf_s.high != 0 ? 64u + hf_bitlen(hf_s.high) : hf_bitlen(hf_s.low);
  int hf_t = (int)((hf_length - 1u) / 2u) - 23;
  int hf_subnormal_grid = -149 - hf_kb;
  if (hf_t < hf_subnormal_grid) hf_t = hf_subnormal_grid;
  unsigned hf_twot = 2u * (unsigned)hf_t;
  uint64_t hf_targ = hf_right(hf_s, hf_twot);
  uint32_t hf_q = hf_isqrt48(hf_targ);
  uint64_t hf_mid = (uint64_t)(2u * hf_q + 1u) * (2u * hf_q + 1u);
  uint64_t hf_upper;
  unsigned hf_sticky;
  if (hf_t == 0) {
    hf_upper = hf_s.low << 2;
    hf_sticky = 0;
  }
  else {
    unsigned hf_cut = hf_twot - 2u;
    hf_upper = hf_right(hf_s, hf_cut);
    hf_sticky = (hf_s.low & ((UINT64_C(1) << hf_cut) - 1u)) != 0;
  }
  if (hf_upper > hf_mid || (hf_upper == hf_mid && (hf_sticky || (hf_q & 1u)))) ++hf_q;
  unsigned hf_qbits = hf_bitlen(hf_q);
  int hf_e = hf_kb + hf_t + (int)hf_qbits - 1;
  if (hf_e >= 128) {
    (void)gmath_overflow(0);
    return hf_value(0x7f800000u);
  }
  uint32_t hf_result;
  if (hf_e >= -126) {
    uint32_t hf_m = hf_qbits > 24 ? hf_q >> (hf_qbits - 24u) : hf_q << (24u - hf_qbits);
    hf_result = ((uint32_t)(hf_e + 127) << 23) | (hf_m & 0x007fffffu);
  }
  else {
    hf_result = hf_q; /* Here kb+t=-149, the subnormal spacing. */
  }
  hypotf_uint96 hf_square = hf_shift((uint64_t)hf_q * hf_q, hf_twot);
  unsigned hf_exact = hf_square.low == hf_s.low && hf_square.high == hf_s.high;
  if (!hf_exact) {
    if (hf_result < 0x00800000u) (void)gmath_underflow(0);
    else hf_inexact();
  }
  return hf_value(hf_result);
}
