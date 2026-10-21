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
 * gmath_decimal_to_double and gmath_decimal_parse: a decimal rounded to the
 * nearest double, ties to even, in integer arithmetic only.
 *
 * The method (documentation/design.md, "Decimal conversion"):
 *
 *  1. The value is D * 10^E for an integer D.  Leading and trailing zeros do
 *     not matter, and neither do digits past the 800th significant one: every
 *     double and every midpoint between two doubles has at most 768
 *     significant digits, so when more than 800 are given, the rounding of the
 *     value is the rounding of the first 800 followed by a 5 (any number
 *     strictly between the truncation and the next 800-digit decimal rounds
 *     alike, because no rounding boundary lies between them).
 *  2. A magnitude of 10^309 or more is infinity, and one below 10^-324 is zero,
 *     decided from the exponent alone.
 *  3. Otherwise the value is A / B with A = D * 10^max(E, 0) and
 *     B = 10^max(-E, 0), and q = floor(A * 2^k / B) is formed with k chosen so
 *     that q has 56 or 57 bits, with a flag for a nonzero remainder.  q and the
 *     flag are rounded once, to 53 bits for a normal result and to fewer for a
 *     subnormal, half to even.
 *
 * Step 3 divides in one of three ways, all exact, chosen by the operands: no
 * division when B is 1 (a whole number), short division when B has one 32-bit
 * limb, and restoring long division otherwise.  The last is the general tier,
 * and the tests force it for every input and require the same bits (AD-13).
 * No floating-point operation is used anywhere, so the rounding mode and the
 * exception flags are never read or changed.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/decimal.h>

#include "bignum.h"
#include "decimal_internal.h"

#include <string.h>

/* The significant digits kept before the rest is replaced by one 5. */
#define GMATH_DECIMAL_KEEP 800

static double gmath_decimal_from_bits(uint64_t u) {
  double d;
  memcpy(&d, &u, sizeof d);
  return d;
}

static char gmath_decimal_digit_at(const char * a, size_t a_length, const char * b,
                                   size_t i) {
  return i < a_length ? a[i] : b[i - a_length];
}

/*
 * exponent + up, saturated at INT64_MAX.  The decimal exponent of the leading
 * digit can only be larger than the last digit's.
 */
static int64_t gmath_decimal_add_saturating(int64_t exponent, uint64_t up) {
  uint64_t room;
  if (exponent >= 0) {
    room = (uint64_t) INT64_MAX - (uint64_t) exponent;
  } else {
    /* INT64_MAX - exponent, which needs 64 unsigned bits. */
    room = (uint64_t) INT64_MAX + (uint64_t) (-(exponent + 1)) + 1u;
  }
  if (up > room) {
    return INT64_MAX;
  }
  if (exponent >= 0) {
    return (int64_t) ((uint64_t) exponent + up);
  }
  /* exponent < 0 and up <= INT64_MAX - exponent, so the sum is in
   * [exponent, INT64_MAX] and neither step below overflows. */
  if (up <= (uint64_t) INT64_MAX) {
    return exponent + (int64_t) up;
  }
  return (exponent + INT64_MAX) + (int64_t) (up - (uint64_t) INT64_MAX);
}

/*
 * Round q * 2^b, with sticky meaning "plus something in (0, 1) units of q",
 * to a double: 53 significant bits for a normal result, fewer for a subnormal,
 * half to even.  q has 56 or 57 bits.
 */
static uint64_t gmath_decimal_round_q(uint64_t q, int64_t b, bool sticky, unsigned * flags) {
  int64_t bq = 0;
  for (uint64_t t = q; t != 0; t >>= 1) {
    bq++;
  }
  int64_t ue = bq - 1 + b; /* the exponent of the leading bit */
  if (ue > 1023) {
    *flags |= GMATH_DECIMAL_OVERFLOW | GMATH_DECIMAL_INEXACT;
    return 0x7ff0000000000000ull;
  }
  bool normal = ue >= -1022;
  int64_t p = normal ? 53 : ue + 1075; /* significand bits the result can hold */
  int64_t drop = bq - p;
  uint64_t mant;
  bool inexact;
  if (drop > 63) {
    /* p < 0: the value is below 2^-1075, half the smallest subnormal. */
    mant = 0;
    inexact = true;
  } else {
    uint64_t rem = q & (((uint64_t) 1 << drop) - 1u);
    uint64_t half = (uint64_t) 1 << (drop - 1);
    mant = q >> drop;
    inexact = rem != 0 || sticky;
    if (rem > half || (rem == half && (sticky || (mant & 1u) != 0))) {
      mant++;
    }
  }
  if (inexact) {
    *flags |= GMATH_DECIMAL_INEXACT;
    if (!normal) {
      *flags |= GMATH_DECIMAL_UNDERFLOW;
    }
  }
  if (!normal) {
    /* The last bit weighs 2^-1074 whatever p is, so the significand is the
     * encoding; a carry to 2^52 is the smallest normal number's. */
    return mant;
  }
  if (mant == ((uint64_t) 1 << 53)) {
    mant >>= 1;
    ue++;
    if (ue > 1023) {
      *flags |= GMATH_DECIMAL_OVERFLOW | GMATH_DECIMAL_INEXACT;
      return 0x7ff0000000000000ull;
    }
  }
  return ((uint64_t) (ue + 1023) << 52) | (mant & 0x000fffffffffffffull);
}

GMATH_Result gmath_decimal_round_spans(bool negative, const char * a, size_t a_length,
                                       const char * b, size_t b_length, int64_t exponent,
                                       bool force_general, double * out, unsigned * flags,
                                       gmath_decimal_tier * tier) {
  if (out == NULL || (a == NULL && a_length != 0) || (b == NULL && b_length != 0) ||
      a_length > SIZE_MAX - b_length) {
    return GMATH_ERR_INVALID;
  }
  size_t total = a_length + b_length;
  if (total == 0) {
    return GMATH_ERR_INVALID;
  }
  /* One pass: check every character, find the first and last nonzero digit. */
  size_t first = total;
  size_t last = 0;
  for (size_t i = 0; i < total; ++i) {
    char c = gmath_decimal_digit_at(a, a_length, b, i);
    if (c < '0' || c > '9') {
      return GMATH_ERR_INVALID;
    }
    if (c != '0') {
      if (first == total) {
        first = i;
      }
      last = i;
    }
  }
  uint64_t sign = negative ? 0x8000000000000000ull : 0u;
  unsigned fl = 0;
  gmath_decimal_tier used = GMATH_DECIMAL_TIER_SPECIAL;
  uint64_t bits;

  if (first == total) {
    bits = sign; /* a zero, of the sign given */
    goto done;
  }

  /* The power of ten of the leading digit. */
  int64_t lead = gmath_decimal_add_saturating(exponent, (uint64_t) (total - 1 - first));
  if (lead >= 309) {
    /* At least 10^309, beyond the largest double (about 1.8 * 10^308) by more
     * than half a unit in the last place. */
    bits = sign | 0x7ff0000000000000ull;
    fl = GMATH_DECIMAL_OVERFLOW | GMATH_DECIMAL_INEXACT;
    goto done;
  }
  if (lead <= -325) {
    /* Below 10^-324, which is below 2^-1075, half the smallest subnormal. */
    bits = sign;
    fl = GMATH_DECIMAL_UNDERFLOW | GMATH_DECIMAL_INEXACT;
    goto done;
  }

  size_t significant = last - first + 1;
  bool sticky = significant > GMATH_DECIMAL_KEEP;
  size_t keep = sticky ? GMATH_DECIMAL_KEEP : significant;

  gmath_big num;
  gmath_big den;
  gmath_big scratch;
  num.n = 0;
  {
    uint32_t chunk = 0;
    unsigned in_chunk = 0;
    for (size_t i = 0; i < keep; ++i) {
      chunk = chunk * 10u + (uint32_t) (gmath_decimal_digit_at(a, a_length, b, first + i) - '0');
      if (++in_chunk == 9) {
        if (!gmath_big_mul_add_u32(&num, 1000000000u, chunk)) {
          return GMATH_ERR_INTERNAL;
        }
        chunk = 0;
        in_chunk = 0;
      }
    }
    if (in_chunk != 0) {
      static const uint32_t pow10[9] = {1u, 10u, 100u, 1000u, 10000u, 100000u, 1000000u,
                                        10000000u, 100000000u};
      if (!gmath_big_mul_add_u32(&num, pow10[in_chunk], chunk)) {
        return GMATH_ERR_INTERNAL;
      }
    }
  }
  if (sticky && !gmath_big_mul_add_u32(&num, 10u, 5u)) {
    return GMATH_ERR_INTERNAL;
  }
  /* The power of ten of the last digit now in num; within [-1125, 308]. */
  int64_t e = lead - (int64_t) (keep - 1) - (sticky ? 1 : 0);

  uint64_t q;
  int64_t bexp;
  bool rest;
  if (e >= 0) {
    /* A whole number: no division. */
    if (!gmath_big_mul_pow10(&num, (unsigned) e)) {
      return GMATH_ERR_INTERNAL;
    }
    size_t la = gmath_big_bitlen(&num);
    if (la >= 57) {
      q = gmath_big_shr_u64(&num, la - 57);
      rest = gmath_big_low_bits_nonzero(&num, la - 57);
      bexp = (int64_t) la - 57;
    } else {
      q = gmath_big_shr_u64(&num, 0) << (57 - la);
      rest = false;
      bexp = (int64_t) la - 57;
    }
    used = GMATH_DECIMAL_TIER_SHIFT;
  } else {
    gmath_big_set_u64(&den, 1u);
    if (!gmath_big_mul_pow10(&den, (unsigned) -e)) {
      return GMATH_ERR_INTERNAL;
    }
    int64_t la = (int64_t) gmath_big_bitlen(&num);
    int64_t lb = (int64_t) gmath_big_bitlen(&den);
    int64_t k = 56 - la + lb; /* puts q in (2^55, 2^57) */
    if (k >= 0) {
      if (!gmath_big_shl(&num, (size_t) k)) {
        return GMATH_ERR_INTERNAL;
      }
    } else if (!gmath_big_shl(&den, (size_t) -k)) {
      return GMATH_ERR_INTERNAL;
    }
    if (den.n == 1 && !force_general) {
      uint32_t r = gmath_big_div_u32(&num, den.limb[0]);
      q = gmath_big_shr_u64(&num, 0);
      rest = r != 0;
      used = GMATH_DECIMAL_TIER_DIV32;
    } else {
      if (!gmath_big_divmod_small_quotient(&num, &den, &scratch, &q)) {
        return GMATH_ERR_INTERNAL;
      }
      rest = !gmath_big_is_zero(&num);
      used = GMATH_DECIMAL_TIER_RESTORING;
    }
    bexp = -k;
  }
  if (q < ((uint64_t) 1 << 55) || q >= ((uint64_t) 1 << 57)) {
    return GMATH_ERR_INTERNAL; /* the bounds of the method say this cannot happen */
  }
  bits = sign | gmath_decimal_round_q(q, bexp, rest, &fl);

done:
  *out = gmath_decimal_from_bits(bits);
  if (flags != NULL) {
    *flags = fl;
  }
  if (tier != NULL) {
    *tier = used;
  }
  return GMATH_OK;
}

GMATH_Result gmath_decimal_to_double(bool negative, const char * digits, size_t length,
                                     int64_t exponent, double * out, unsigned * flags) {
  if (digits == NULL || length == 0) {
    return GMATH_ERR_INVALID;
  }
  return gmath_decimal_round_spans(negative, digits, length, NULL, 0, exponent, false, out,
                                   flags, NULL);
}

/* An exponent saturates here; with lengths below 2^62, nothing larger can
 * change a result, and the arithmetic below cannot overflow. */
#define GMATH_DECIMAL_EXPONENT_CAP ((int64_t) 1 << 61)

GMATH_Result gmath_decimal_parse(const char * text, size_t length, double * out,
                                 size_t * consumed, unsigned * flags) {
  uint64_t length64 = length;
  if (out == NULL || (text == NULL && length != 0) || length64 > ((uint64_t) 1 << 62)) {
    return GMATH_ERR_INVALID;
  }
  size_t i = 0;
  bool negative = false;
  if (i < length && (text[i] == '+' || text[i] == '-')) {
    negative = text[i] == '-';
    i++;
  }
  size_t int_start = i;
  while (i < length && text[i] >= '0' && text[i] <= '9') {
    i++;
  }
  size_t int_length = i - int_start;
  size_t frac_start = i;
  size_t frac_length = 0;
  if (i < length && text[i] == '.') {
    size_t j = i + 1;
    while (j < length && text[j] >= '0' && text[j] <= '9') {
      j++;
    }
    /* A point with no digit on either side is refused below. */
    frac_start = i + 1;
    frac_length = j - (i + 1);
    i = j;
  }
  if (int_length == 0 && frac_length == 0) {
    return GMATH_ERR_FORMAT;
  }
  int64_t exp10 = 0;
  if (i < length && (text[i] == 'e' || text[i] == 'E')) {
    size_t j = i + 1;
    bool exp_negative = false;
    if (j < length && (text[j] == '+' || text[j] == '-')) {
      exp_negative = text[j] == '-';
      j++;
    }
    if (j < length && text[j] >= '0' && text[j] <= '9') {
      while (j < length && text[j] >= '0' && text[j] <= '9') {
        int d = text[j] - '0';
        if (exp10 <= (GMATH_DECIMAL_EXPONENT_CAP - 9) / 10) {
          exp10 = exp10 * 10 + d;
        } else {
          exp10 = GMATH_DECIMAL_EXPONENT_CAP;
        }
        j++;
      }
      if (exp_negative) {
        exp10 = -exp10;
      }
      i = j;
    }
  }
  /* The power of ten of the last digit given. */
  int64_t last_exponent = exp10 - (int64_t) frac_length;
  unsigned fl = 0;
  GMATH_Result r = gmath_decimal_round_spans(negative, text + int_start, int_length,
                                             frac_length != 0 ? text + frac_start : NULL,
                                             frac_length, last_exponent, false, out, &fl, NULL);
  if (r != GMATH_OK) {
    return r;
  }
  if (consumed != NULL) {
    *consumed = i;
  }
  if (flags != NULL) {
    *flags = fl;
  }
  return GMATH_OK;
}
