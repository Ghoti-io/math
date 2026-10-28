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
 * Nearest positive difference from exact fixed-limb integer arithmetic.
 * WG14 N1570 7.12.12.1/F.10.9.1; see documentation/design.md for the
 * deterministic rounding and explicit exception policy.
 */
#include "elem_common.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <limits.h>

GMATH_STATIC_ASSERT(sizeof(double) == sizeof(uint64_t) && FLT_RADIX == 2 &&
    DBL_MANT_DIG == 53 && DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
    "positive difference requires IEEE binary64");
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_MANT_DIG == 24 &&
    FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
    "Float positive difference requires IEEE binary32");

/* Nonzero input only. Integer counting never touches the floating state. */
static unsigned pd_top(uint64_t x) {
#if (defined(__GNUC__) || defined(__clang__)) && ULLONG_MAX == UINT64_MAX && \
    !defined(GMATH_FDIM_PORTABLE_BITS)
  return 63u - (unsigned)__builtin_clzll((unsigned long long)x);
#else
  unsigned n = 0;
  while (x >> 1) {
    x >>= 1;
    ++n;
  }
  return n;
#endif
}
static void pd_unpack(uint64_t a, unsigned p, int bias,
    uint64_t * m, int * e) {
  unsigned field = (unsigned)(a >> p);
  uint64_t hidden = UINT64_C(1) << p;
  if (field) {
    *e = (int)field - bias;
    *m = hidden | (a & (hidden - 1));
  } else {
    unsigned shift = p - pd_top(a);
    *e = 1 - bias - (int)shift;
    *m = a << shift;
  }
}
/* Internal flag classes: invalid1, inexact2, overflow4. Raw dispatch avoids
 * quieting a signaling input before the public operation can classify it.
 */
static uint64_t pd_core(uint64_t x, uint64_t y, unsigned p, unsigned eb,
    int bias, unsigned * flags) {
  uint64_t sign = UINT64_C(1) << (p + eb);
  uint64_t ax = x & (sign - 1), ay = y & (sign - 1);
  uint64_t inf = ((UINT64_C(1) << eb) - 1) << p;
  uint64_t quiet = UINT64_C(1) << (p - 1), hidden = UINT64_C(1) << p;
  *flags = 0;
  if (ax > inf || ay > inf) {
    *flags = ((ax > inf && !(x & quiet)) ||
        (ay > inf && !(y & quiet))) ? 1u : 0u;
    return inf | quiet;
  }
  if (!ax && !ay) {
    return 0;
  }
  uint64_t kx = (x & sign) ? (sign - 1) - ax : sign + ax;
  uint64_t ky = (y & sign) ? (sign - 1) - ay : sign + ay;
  if (kx <= ky) {
    return 0;
  }
  if (ax == inf || ay == inf) {
    return inf;
  }
  if (!ax) {
    return ay;
  }
  if (!ay) {
    return ax;
  }
  uint64_t a = ax > ay ? ax : ay, b = ax > ay ? ay : ax, ma, mb;
  int ea, ebv;
  pd_unpack(a, p, bias, &ma, &ea);
  pd_unpack(b, p, bias, &mb, &ebv);
  unsigned gap = (unsigned)(ea - ebv);
  /* The smallest midpoint distance is below a power of two, where the
   * predecessor spacing halves. Precision P=p+1 needs gap>=P+2, not P+1.
   */
  if (gap >= p + 3u) {
    *flags = 2;
    return a;
  }
  /* At most (p+1)+(p+2)=107 bits. Every alignment shift is below64. */
  uint64_t lo = ma << gap, hi = gap ? ma >> (64u - gap) : 0, old = lo;
  if ((x ^ y) & sign) {
    lo += mb;
    hi += lo < old;
  } else {
    lo -= mb;
    hi -= old < mb;
  }
  unsigned top = hi ? 64u + pd_top(hi) : pd_top(lo);
  int e = ebv - (int)p + (int)top;
  uint64_t q, lost = 0;
  if (top > p) {
    unsigned cut = top - p; /* 1..54; all discarded bits lie in lo. */
    lost = lo & ((UINT64_C(1) << cut) - 1);
    q = (lo >> cut) | (hi << (64u - cut));
    uint64_t half = UINT64_C(1) << (cut - 1);
    q += lost > half || (lost == half && (q & 1));
  } else {
    q = lo << (p - top);
  }
  if (q == (hidden << 1)) {
    q >>= 1;
    ++e;
  }
  if (e > bias) {
    *flags = 6;
    return inf;
  }
  if (lost) {
    *flags = 2;
  }
  if (e < 1 - bias) {
    /* A difference below minimum normal lies on the subnormal lattice:
     * lost==0 and this shift (at most p) discards only zeros. */
    return q >> (unsigned)(1 - bias - e);
  }
  return ((uint64_t)(e + bias) << p) | (q & (hidden - 1));
}
static void pd_raise(unsigned flags) {
  if (flags & 1u) {
    (void)gmath_invalid();
  } else if (flags & 4u) {
    (void)gmath_overflow(0);
  } else if (flags & 2u) {
    volatile double one = 1.0, tiny = 0x1p-54;
    volatile double ignored = one + tiny;
    (void)ignored;
  }
}
double gmath_fdim(double x, double y) {
  unsigned flags;
  uint64_t result = pd_core(gmath_bits(x), gmath_bits(y), 52, 11, 1023, &flags);
  pd_raise(flags);
  return gmath_double(result);
}
float gmath_fdimf(float x, float y) {
  uint32_t bx, by;
  memcpy(&bx, &x, sizeof bx);
  memcpy(&by, &y, sizeof by);
  unsigned flags;
  uint32_t result = (uint32_t)pd_core(bx, by, 23, 8, 127, &flags);
  pd_raise(flags);
  float output;
  memcpy(&output, &result, sizeof output);
  return output;
}
