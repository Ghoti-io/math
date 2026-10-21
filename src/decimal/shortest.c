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
 * gmath_decimal_shortest: the shortest decimal that rounds back to a double,
 * in integer arithmetic only.
 *
 * The decimals that gmath_decimal_to_double rounds to x are those in the
 * interval between the midpoints next to x: (x - g_lo, x + g_hi), with both
 * ends included when x's significand is even (a tie goes to the even
 * neighbour, which is x) and excluded when it is odd.  g_hi is half a unit in
 * the last place; g_lo is the same, except that below a power of two (other
 * than the smallest normal) the gap to the predecessor is half as wide.
 *
 * Every value is a multiple of 2^(e - 2), where x = m * 2^e: x is 4m, the upper
 * end 4m + 2, the lower end 4m - 2 or 4m - 1.  With L the power of ten of x's
 * leading digit and s = L - 16, each is divided once, exactly, by 10^s, giving
 * a 17-digit integer part and a flag for a nonzero remainder (for x, the
 * remainder's comparison with one half).  For n = 1, 2, ..., 17 the candidates
 * with n significant digits are the integers c in the scaled interval divided
 * by 10^(17 - n); those bounds and the one nearest x follow from the 17-digit
 * parts and the flags by integer division.  The first n with a candidate is the
 * shortest length, and the candidate nearest x (half to even) is the answer.
 * Seventeen digits always suffice: the interval is wider than one unit there
 * (documentation/design.md, "Decimal conversion").
 *
 * Two fast tiers, each checked against the general one on every corpus input
 * and shown taken (AD-13).  An integer of magnitude below 2^53 is its own
 * answer: its interval is at most one unit wide, so no shorter decimal lies in
 * it.  And when the divisor 2^(2 - e) * 10^s is a power of two (s <= 0, which is
 * every |x| below 10^16, and e < 2), the three divisions are shifts.  A divisor
 * of one 32-bit limb is divided short; anything else by restoring division, the
 * general tier.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/decimal.h>

#include "bignum.h"
#include "decimal_internal.h"

#include <string.h>

static const uint64_t gmath_decimal_pow10_u64[18] = {
    1ull,
    10ull,
    100ull,
    1000ull,
    10000ull,
    100000ull,
    1000000ull,
    10000000ull,
    100000000ull,
    1000000000ull,
    10000000000ull,
    100000000000ull,
    1000000000000ull,
    10000000000000ull,
    100000000000000ull,
    1000000000000000ull,
    10000000000000000ull,
    100000000000000000ull,
};

/* Write c (nonzero) times 10^exponent, without trailing zeros. */
static void gmath_decimal_emit(uint64_t c, int exponent, GMATH_Decimal * out) {
  while (c % 10u == 0) {
    c /= 10u;
    exponent++;
  }
  char buf[24];
  size_t n = 0;
  while (c != 0) {
    buf[n++] = (char) ('0' + (int) (c % 10u));
    c /= 10u;
  }
  for (size_t i = 0; i < n; ++i) {
    out->digits[i] = buf[n - 1 - i];
  }
  out->digits[n] = '\0';
  out->length = n;
  out->exponent = exponent;
}

/*
 * floor(v * 2^f / 10^s) with a flag for a nonzero remainder and, when half is
 * not NULL, the comparison of the remainder with one half of the divisor.
 */
static bool gmath_decimal_scaled(uint64_t v, int f, int s, bool force_general, uint64_t * q,
                                 bool * rest, int * half, gmath_decimal_tier * tier) {
  gmath_big num;
  gmath_big den;
  gmath_big scratch;
  gmath_big_set_u64(&num, v);
  gmath_big_set_u64(&den, 1u);
  if (f >= 0) {
    if (!gmath_big_shl(&num, (size_t) f)) {
      return false;
    }
  } else if (!gmath_big_shl(&den, (size_t) -f)) {
    return false;
  }
  if (s >= 0) {
    if (!gmath_big_mul_pow10(&den, (unsigned) s)) {
      return false;
    }
  } else if (!gmath_big_mul_pow10(&num, (unsigned) -s)) {
    return false;
  }
  if (s <= 0 && f < 0 && !force_general) {
    /* The divisor is 2^-f: the quotient is a shift and the remainder its low
     * bits; one half of the divisor is bit -f - 1. */
    size_t k = (size_t) -f;
    if (gmath_big_bitlen(&num) > k + 63) {
      return false;
    }
    *q = gmath_big_shr_u64(&num, k);
    *rest = gmath_big_low_bits_nonzero(&num, k);
    if (half != NULL) {
      bool top = (gmath_big_shr_u64(&num, k - 1) & 1u) != 0;
      bool below = gmath_big_low_bits_nonzero(&num, k - 1);
      *half = top ? (below ? 1 : 0) : -1;
    }
    *tier = GMATH_DECIMAL_TIER_SHIFT;
    return true;
  }
  if (den.n == 1 && !force_general) {
    uint32_t d = den.limb[0];
    uint32_t r = gmath_big_div_u32(&num, d);
    if (gmath_big_bitlen(&num) > 63) {
      return false;
    }
    *q = gmath_big_shr_u64(&num, 0);
    *rest = r != 0;
    if (half != NULL) {
      uint64_t twice = (uint64_t) r * 2u;
      *half = twice < d ? -1 : (twice == d ? 0 : 1);
    }
    *tier = GMATH_DECIMAL_TIER_DIV32;
    return true;
  }
  if (!gmath_big_divmod_small_quotient(&num, &den, &scratch, q)) {
    return false;
  }
  *rest = !gmath_big_is_zero(&num);
  if (half != NULL) {
    if (!gmath_big_shl(&num, 1)) {
      return false;
    }
    *half = gmath_big_cmp(&num, &den);
  }
  *tier = GMATH_DECIMAL_TIER_RESTORING;
  return true;
}

GMATH_Result gmath_decimal_shortest_tiered(double x, bool force_general, GMATH_Decimal * out,
                                           gmath_decimal_tier * tier) {
  if (out == NULL) {
    return GMATH_ERR_INVALID;
  }
  uint64_t bits;
  memcpy(&bits, &x, sizeof bits);
  unsigned biased = (unsigned) ((bits >> 52) & 0x7ffu);
  uint64_t frac = bits & 0x000fffffffffffffull;
  if (biased == 0x7ffu) {
    return GMATH_ERR_INVALID; /* an infinity or a NaN */
  }
  GMATH_Decimal d;
  memset(&d, 0, sizeof d);
  d.negative = (bits >> 63) != 0;
  if (biased == 0 && frac == 0) {
    d.digits[0] = '0';
    d.length = 1;
    d.exponent = 0;
    *out = d;
    if (tier != NULL) {
      *tier = GMATH_DECIMAL_TIER_SPECIAL;
    }
    return GMATH_OK;
  }
  uint64_t m = biased == 0 ? frac : (frac | ((uint64_t) 1 << 52));
  int e = biased == 0 ? -1074 : (int) biased - 1075;

  /* The fast tier: an integer below 2^53. */
  if (!force_general && e <= 0 && e >= -52 &&
      (e == 0 || (m & (((uint64_t) 1 << -e) - 1u)) == 0)) {
    gmath_decimal_emit(m >> -e, 0, &d);
    *out = d;
    if (tier != NULL) {
      *tier = GMATH_DECIMAL_TIER_INTEGER;
    }
    return GMATH_OK;
  }

  bool inclusive = (m & 1u) == 0;
  bool closer_below = frac == 0 && biased > 1;
  uint64_t vx = 4u * m;
  uint64_t vh = vx + 2u;
  uint64_t vl = closer_below ? vx - 1u : vx - 2u;
  int f = e - 2;

  /* L, the power of ten of the leading digit: an estimate from the binary
   * exponent within one, then corrected by the size of the quotient. */
  int bitlen = 0;
  for (uint64_t t = m; t != 0; t >>= 1) {
    bitlen++;
  }
  int e2 = bitlen - 1 + e; /* 2^e2 <= x < 2^(e2 + 1) */
  /* floor(e2 * log10(2)), within one: 78913 / 2^18 is 0.30102920..., and
   * |e2| <= 1074. */
  int64_t prod = (int64_t) e2 * 78913;
  int lead = (int) (prod >= 0 ? prod / 262144 : -((-prod + 262143) / 262144));
  uint64_t qx = 0;
  bool rx = false;
  int hx = 0;
  int s = 0;
  gmath_decimal_tier division = GMATH_DECIMAL_TIER_RESTORING;
  for (int attempt = 0;; ++attempt) {
    if (attempt > 3) {
      return GMATH_ERR_INTERNAL;
    }
    s = lead - 16;
    if (!gmath_decimal_scaled(vx, f, s, force_general, &qx, &rx, &hx, &division)) {
      return GMATH_ERR_INTERNAL;
    }
    if (qx >= gmath_decimal_pow10_u64[17]) {
      lead++;
    } else if (qx < gmath_decimal_pow10_u64[16]) {
      lead--;
    } else {
      break;
    }
  }
  uint64_t ql;
  uint64_t qh;
  bool rl;
  bool rh;
  gmath_decimal_tier ignored;
  if (!gmath_decimal_scaled(vl, f, s, force_general, &ql, &rl, NULL, &ignored) ||
      !gmath_decimal_scaled(vh, f, s, force_general, &qh, &rh, NULL, &ignored)) {
    return GMATH_ERR_INTERNAL;
  }

  for (int n = 1; n <= 17; ++n) {
    int k = 17 - n;
    uint64_t p = gmath_decimal_pow10_u64[k];
    uint64_t lo_q = ql / p;
    bool lo_exact = ql % p == 0 && !rl;
    uint64_t c_lo = (lo_exact && inclusive) ? lo_q : lo_q + 1u;
    uint64_t hi_q = qh / p;
    bool hi_exact = qh % p == 0 && !rh;
    if (hi_exact && !inclusive && hi_q == 0) {
      continue;
    }
    uint64_t c_hi = (hi_exact && !inclusive) ? hi_q - 1u : hi_q;
    if (c_lo > c_hi) {
      continue;
    }
    uint64_t c = qx / p;
    uint64_t r = qx % p;
    bool up;
    if (k == 0) {
      up = hx > 0 || (hx == 0 && (c & 1u) != 0);
    } else {
      uint64_t half = p / 2u;
      up = r > half || (r == half && (rx || (c & 1u) != 0));
    }
    c += up ? 1u : 0u;
    if (c < c_lo) {
      c = c_lo;
    } else if (c > c_hi) {
      c = c_hi;
    }
    gmath_decimal_emit(c, s + k, &d);
    *out = d;
    if (tier != NULL) {
      /* The search, by the way its divisions were made. */
      *tier = division == GMATH_DECIMAL_TIER_RESTORING ? GMATH_DECIMAL_TIER_GENERAL : division;
    }
    return GMATH_OK;
  }
  return GMATH_ERR_INTERNAL; /* seventeen digits always suffice */
}

GMATH_Result gmath_decimal_shortest(double x, GMATH_Decimal * out) {
  return gmath_decimal_shortest_tiered(x, false, out, NULL);
}
