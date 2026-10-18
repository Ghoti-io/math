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
 * gmath_floor, gmath_ceil, gmath_trunc, gmath_round, gmath_rint, gmath_fabs and
 * gmath_copysign, on the bit pattern and, where a result is one more or less
 * than a truncated integer, on an addition that is exact.  Each of them has one
 * correct answer, so these are exact by construction, not within an error; the
 * oracle is the exact reference (tests/corpus, gen_corpus_exact.py).  None of
 * them reads the rounding mode: rint is half to even, round half away from
 * zero.
 *
 * With e the unbiased exponent of |x| and 0 <= e <= 51, the low 52 - e stored
 * bits are the fraction; a larger |x| (and infinity) is an integer already and
 * a smaller one has no integer part.  Every NaN returned is the library's
 * quiet NaN (a signalling NaN raises invalid, as IEEE 754 wants; no other
 * exception is raised), and a zero keeps its sign: floor(-0) is -0, ceil of
 * anything in (-1, 0) is -0, round and rint of a magnitude below one half are
 * the zero of x's sign.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/basic.h>

#include "elem_common.h"

#define GMATH_MANT_MASK 0x000fffffffffffffull
#define GMATH_ONE_BITS 0x3ff0000000000000ull
#define GMATH_HALF_BITS 0x3fe0000000000000ull
#define GMATH_TWO52_BITS 0x4330000000000000ull
/* One half unit in the last place of a number of exponent 0, as stored bits: 2^51. */
#define GMATH_HALF_UNIT 0x0008000000000000ull

double gmath_fabs(double x) {
  uint64_t a = gmath_bits(x) & GMATH_ABS_MASK;
  return a > GMATH_INF_BITS ? gmath_nan_of(x) : gmath_double(a);
}

double gmath_copysign(double x, double y) {
  uint64_t a = gmath_bits(x) & GMATH_ABS_MASK;
  if (a > GMATH_INF_BITS) {
    return gmath_nan_of(x);
  }
  return gmath_double(a | (gmath_bits(y) & GMATH_SIGN_BIT));
}

/* The mask of the bits to keep when the fraction of |x| < 2^52 is dropped: for 0 <= e <= 51 the stored bits above
 * the low 52 - e; for |x| < 1 (e < 0) only the sign.  Computed without a branch: which side of 1 a magnitude
 * falls on is as likely to be decided by the data as not, and a mispredicted branch costs more than the whole
 * function.  (For e < 0 or e > 51 the shifted mask is garbage and is selected away.) */
static inline uint64_t gmath_keep_mask(uint64_t a) {
  uint64_t e = (a >> 52) - 1023; /* wraps for |x| < 1 */
  uint64_t neg = (uint64_t)0 - (e >> 63);
  uint64_t frac = ((GMATH_MANT_MASK >> (e & 63u)) & ~neg) | (GMATH_ABS_MASK & neg);
  return ~frac;
}

double gmath_trunc(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_TWO52_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  return gmath_double(b & gmath_keep_mask(a));
}

/* floor and ceil: the magnitude with its fraction dropped, plus one when the fraction was nonzero and the direction is
 * away from zero (down for a negative number, up for a positive one), then the sign.  The addition is of 1.0 to an integer
 * below 2^52, which is exact, and adds +0 otherwise; the sign is put back on the bit pattern afterwards, so a zero result
 * is -0 for floor(-0), and for ceil(x) with -1 < x < 0, as Annex F says. */
static inline double gmath_floor_or_ceil(uint64_t b, uint64_t a, uint64_t away_sign) {
  uint64_t keep = gmath_keep_mask(a);
  uint64_t has_frac = (uint64_t)((a & ~keep) != 0);
  /* away_sign is the sign bit (as 0 or 1) of the numbers that move away from zero */
  uint64_t add = (uint64_t)0 - (has_frac & (((b >> 63) ^ away_sign) ^ 1u));
  double mag = gmath_double(a & keep) + gmath_double(GMATH_ONE_BITS & add);
  return gmath_double(gmath_bits(mag) | (b & GMATH_SIGN_BIT));
}

double gmath_floor(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_TWO52_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  return gmath_floor_or_ceil(b, a, 1u);
}

double gmath_ceil(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_TWO52_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  return gmath_floor_or_ceil(b, a, 0u);
}

double gmath_round(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_TWO52_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  if (a < GMATH_HALF_BITS) {
    return gmath_double(b & GMATH_SIGN_BIT);
  }
  if (a < GMATH_ONE_BITS) {
    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);
  }
  uint64_t e = (a >> 52) - 1023;
  /* add one half to the magnitude (a carry into the exponent is right), then drop the fraction */
  b += GMATH_HALF_UNIT >> e;
  return gmath_double(b & ~(GMATH_MANT_MASK >> e));
}

double gmath_rint(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_TWO52_BITS) {
    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;
  }
  /* |x| < 1: 1 if |x| is above one half, else 0 (exactly one half is a tie, and the even integer is 0); the sign stays */
  uint64_t sign = b & GMATH_SIGN_BIT;
  uint64_t r_small = sign | (GMATH_ONE_BITS & ((uint64_t)0 - (uint64_t)(a > GMATH_HALF_BITS)));
  /* |x| >= 1, 0 <= e <= 51 (for a smaller magnitude e wraps and these are garbage, selected away below, which is why
   * every shift is masked to 63 and there is no branch on the data) */
  uint64_t e = (a >> 52) - 1023;
  uint64_t frac_mask = GMATH_MANT_MASK >> (e & 63u);
  uint64_t half = GMATH_HALF_UNIT >> (e & 63u);
  uint64_t fr = b & frac_mask;
  uint64_t t = b & ~frac_mask;
  /* the integer's low bit is bit 52 - e of the pattern (the exponent's lowest bit for e = 0).  Round up when the
   * fraction is more than a half, or a half and the integer is odd. */
  uint64_t odd = (t >> ((52u - e) & 63u)) & 1u;
  uint64_t up = (uint64_t)(fr > half) | ((uint64_t)(fr == half) & odd);
  uint64_t r_big = t + ((half << 1) & ((uint64_t)0 - up));
  uint64_t small = (uint64_t)0 - (uint64_t)(a < GMATH_ONE_BITS);
  return gmath_double((r_small & small) | (r_big & ~small));
}
