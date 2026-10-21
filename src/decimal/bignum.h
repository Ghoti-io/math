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
 * A fixed-capacity unsigned integer for the exact decimal conversions
 * (decimal.h).  Little-endian 32-bit limbs, no allocation, no floating point:
 * every operation is integer arithmetic, so a result does not depend on the
 * target, the compiler or the rounding mode.
 *
 * The capacity is fixed by the largest operand the conversions can form, which
 * documentation/design.md bounds ("Decimal conversion"): 10^1125 has 3,738 bits
 * and the dividend is at most 58 bits wider, so 4,096 bits leave a margin.  An
 * operation that would pass the capacity fails rather than wrap, and the caller
 * turns that into GMATH_ERR_INTERNAL; the bounds say it cannot happen.
 */

#ifndef GHOTI_IO_GMATH_SRC_DECIMAL_BIGNUM_H
#define GHOTI_IO_GMATH_SRC_DECIMAL_BIGNUM_H

#include <ghoti.io/math/macros.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define GMATH_BIG_LIMBS 128

typedef struct {
  uint32_t limb[GMATH_BIG_LIMBS];
  size_t n; /* limbs in use; limb[n - 1] != 0 unless n == 0 (the value 0) */
} gmath_big;

static inline void gmath_big_trim(gmath_big * a) {
  while (a->n > 0 && a->limb[a->n - 1] == 0) {
    a->n--;
  }
}

static inline void gmath_big_set_u64(gmath_big * a, uint64_t v) {
  a->limb[0] = (uint32_t) v;
  a->limb[1] = (uint32_t) (v >> 32);
  a->n = 2;
  gmath_big_trim(a);
}

static inline bool gmath_big_is_zero(const gmath_big * a) {
  return a->n == 0;
}

/* a = a * m + add. */
static inline bool gmath_big_mul_add_u32(gmath_big * a, uint32_t m, uint32_t add) {
  uint64_t carry = add;
  for (size_t i = 0; i < a->n; ++i) {
    uint64_t t = (uint64_t) a->limb[i] * m + carry;
    a->limb[i] = (uint32_t) t;
    carry = t >> 32;
  }
  if (carry != 0) {
    if (a->n == GMATH_BIG_LIMBS) {
      return false;
    }
    a->limb[a->n++] = (uint32_t) carry;
  }
  return true;
}

/* a = a * 10^k. */
static inline bool gmath_big_mul_pow10(gmath_big * a, unsigned k) {
  static const uint32_t pow10[10] = {1u, 10u, 100u, 1000u, 10000u, 100000u, 1000000u,
                                     10000000u, 100000000u, 1000000000u};
  if (a->n == 0) {
    return true;
  }
  while (k >= 9) {
    if (!gmath_big_mul_add_u32(a, pow10[9], 0)) {
      return false;
    }
    k -= 9;
  }
  return k == 0 || gmath_big_mul_add_u32(a, pow10[k], 0);
}

/* a = a * 2^k. */
static inline bool gmath_big_shl(gmath_big * a, size_t k) {
  if (a->n == 0 || k == 0) {
    return true;
  }
  size_t words = k / 32;
  unsigned bits = (unsigned) (k % 32);
  uint32_t high = a->limb[a->n - 1];
  size_t top_bits = 0;
  while (high != 0) {
    top_bits++;
    high >>= 1;
  }
  /* The result's bit length is (n - 1) * 32 + top_bits + k. */
  if (k > (size_t) GMATH_BIG_LIMBS * 32 ||
      (a->n - 1) * 32 + top_bits + k > (size_t) GMATH_BIG_LIMBS * 32) {
    return false;
  }
  if (bits == 0) {
    for (size_t i = a->n; i-- > 0;) {
      a->limb[i + words] = a->limb[i];
    }
  } else {
    uint32_t top = a->limb[a->n - 1] >> (32 - bits);
    if (top != 0) {
      a->limb[a->n + words] = top;
    }
    for (size_t i = a->n - 1; i > 0; --i) {
      a->limb[i + words] = (a->limb[i] << bits) | (a->limb[i - 1] >> (32 - bits));
    }
    a->limb[words] = a->limb[0] << bits;
    if (top != 0) {
      a->n++;
    }
  }
  for (size_t i = 0; i < words; ++i) {
    a->limb[i] = 0;
  }
  a->n += words;
  return true;
}

/* a = floor(a / 2). */
static inline void gmath_big_shr1(gmath_big * a) {
  for (size_t i = 0; i + 1 < a->n; ++i) {
    a->limb[i] = (a->limb[i] >> 1) | (a->limb[i + 1] << 31);
  }
  if (a->n > 0) {
    a->limb[a->n - 1] >>= 1;
    gmath_big_trim(a);
  }
}

/* -1, 0 or 1 as a <, ==, > b. */
static inline int gmath_big_cmp(const gmath_big * a, const gmath_big * b) {
  if (a->n != b->n) {
    return a->n < b->n ? -1 : 1;
  }
  for (size_t i = a->n; i-- > 0;) {
    if (a->limb[i] != b->limb[i]) {
      return a->limb[i] < b->limb[i] ? -1 : 1;
    }
  }
  return 0;
}

/* a = a - b, which requires a >= b. */
static inline void gmath_big_sub(gmath_big * a, const gmath_big * b) {
  uint64_t borrow = 0;
  size_t i = 0;
  for (; i < b->n; ++i) {
    uint64_t t = (uint64_t) a->limb[i] - b->limb[i] - borrow;
    a->limb[i] = (uint32_t) t;
    borrow = (t >> 32) & 1u;
  }
  for (; borrow != 0 && i < a->n; ++i) {
    uint64_t t = (uint64_t) a->limb[i] - borrow;
    a->limb[i] = (uint32_t) t;
    borrow = (t >> 32) & 1u;
  }
  gmath_big_trim(a);
}

/* The number of significant bits; 0 for 0. */
static inline size_t gmath_big_bitlen(const gmath_big * a) {
  if (a->n == 0) {
    return 0;
  }
  uint32_t top = a->limb[a->n - 1];
  size_t bits = 0;
  while (top != 0) {
    bits++;
    top >>= 1;
  }
  return (a->n - 1) * 32 + bits;
}

/* Whether any of the low k bits of a is set. */
static inline bool gmath_big_low_bits_nonzero(const gmath_big * a, size_t k) {
  size_t words = k / 32;
  unsigned bits = (unsigned) (k % 32);
  for (size_t i = 0; i < words && i < a->n; ++i) {
    if (a->limb[i] != 0) {
      return true;
    }
  }
  return bits != 0 && words < a->n && (a->limb[words] & ((1u << bits) - 1u)) != 0;
}

/* floor(a / 2^k) mod 2^64; the caller guarantees the quotient fits. */
static inline uint64_t gmath_big_shr_u64(const gmath_big * a, size_t k) {
  size_t w = k / 32;
  unsigned bits = (unsigned) (k % 32);
  uint64_t lo = w < a->n ? a->limb[w] : 0u;
  uint64_t mid = w + 1 < a->n ? a->limb[w + 1] : 0u;
  uint64_t hi = w + 2 < a->n ? a->limb[w + 2] : 0u;
  uint64_t low64 = lo | (mid << 32);
  if (bits == 0) {
    return low64;
  }
  return (low64 >> bits) | (hi << (64 - bits));
}

/* a = floor(a / d), returning a mod d; d != 0. */
static inline uint32_t gmath_big_div_u32(gmath_big * a, uint32_t d) {
  uint64_t rem = 0;
  for (size_t i = a->n; i-- > 0;) {
    uint64_t cur = (rem << 32) | a->limb[i];
    a->limb[i] = (uint32_t) (cur / d);
    rem = cur % d;
  }
  gmath_big_trim(a);
  return (uint32_t) rem;
}

/*
 * q = floor(a / b) and a = a mod b, by restoring binary long division, for a
 * quotient below 2^63 (the caller's bounds guarantee it: false otherwise).
 * b != 0.  scratch is overwritten.
 */
static inline bool gmath_big_divmod_small_quotient(gmath_big * a, const gmath_big * b,
                                                   gmath_big * scratch, uint64_t * q) {
  size_t la = gmath_big_bitlen(a);
  size_t lb = gmath_big_bitlen(b);
  *q = 0;
  if (la < lb) {
    return true;
  }
  size_t top = la - lb; /* the quotient has at most top + 1 bits */
  if (top > 62) {
    return false;
  }
  *scratch = *b;
  if (!gmath_big_shl(scratch, top)) {
    return false;
  }
  for (size_t i = top + 1; i-- > 0;) {
    if (gmath_big_cmp(a, scratch) >= 0) {
      gmath_big_sub(a, scratch);
      *q |= (uint64_t) 1 << i;
    }
    gmath_big_shr1(scratch);
  }
  return true;
}

#endif /* GHOTI_IO_GMATH_SRC_DECIMAL_BIGNUM_H */
