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
 * Private helpers of explog.c, atan2.c and hypot.c: the bit-level accessors,
 * the error-free transformations of Knuth and Dekker (Muller, Elementary
 * Functions, chapter 4), the canonical quiet NaN and the exception-raising
 * results.  Everything is IEEE addition, subtraction, multiplication and
 * division on double, and integer operations; the library is built with
 * -ffp-contract=off.  The unit tests include the .c files as C++, so every
 * name here is `static` and the file may be included by only one .c file of a
 * translation unit.
 */

#ifndef GHOTI_IO_GMATH_ELEM_COMMON_H
#define GHOTI_IO_GMATH_ELEM_COMMON_H

#include <ghoti.io/math/macros.h>

#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
#define GMATH_ALIGN16 alignas(16)
#define GMATH_STATIC_ASSERT(c, m) static_assert(c, m)
#else
#define GMATH_ALIGN16 _Alignas(16)
#define GMATH_STATIC_ASSERT(c, m) _Static_assert(c, m)
#endif

/* Macros, not constants: atan2.c uses them in the initializer of a static table. */
#define GMATH_SIGN_BIT 0x8000000000000000ull
#define GMATH_ABS_MASK 0x7fffffffffffffffull
#define GMATH_INF_BITS 0x7ff0000000000000ull
#define GMATH_QNAN_BITS 0x7ff8000000000000ull

static inline uint64_t gmath_bits(double d) {
  uint64_t u;
  memcpy(&u, &d, sizeof u);
  return u;
}

static inline double gmath_double(uint64_t u) {
  double d;
  memcpy(&d, &u, sizeof d);
  return d;
}

/* A double-double: hi + lo. */
typedef struct {
  double hi;
  double lo;
} gmath_pair;

/* Knuth's FastTwoSum, valid when |a| >= |b| or a == 0: s + e == a + b exactly,
 * s = fl(a + b).  It is also exact whenever a + b is exactly representable. */
static inline gmath_pair gmath_fast_two_sum(double a, double b) {
  gmath_pair r;
  double s = a + b;
  r.hi = s;
  r.lo = b - (s - a);
  return r;
}

/* Knuth's TwoSum: s + e == a + b exactly, in any order of magnitudes. */
static inline gmath_pair gmath_two_sum(double a, double b) {
  gmath_pair r;
  double s = a + b;
  double bb = s - a;
  r.hi = s;
  r.lo = (a - (s - bb)) + (b - bb);
  return r;
}

/* Veltkamp's split: a == hi + lo, each with at most 26 significant bits. */
static inline void gmath_split(double a, double * hi, double * lo) {
  double t = 134217729.0 * a; /* 2^27 + 1 */
  double h = t - (t - a);
  *hi = h;
  *lo = a - h;
}

/* Dekker's product: p + e == a * b exactly, p = fl(a * b), barring overflow and
 * underflow of the partial products. */
static inline gmath_pair gmath_two_prod(double a, double b) {
  gmath_pair r;
  double ah, al, bh, bl;
  double p = a * b;
  gmath_split(a, &ah, &al);
  gmath_split(b, &bh, &bl);
  r.hi = p;
  r.lo = ((ah * bh - p) + ah * bl + al * bh) + al * bl;
  return r;
}

/* The same for a * a, with one split. */
static inline gmath_pair gmath_two_sqr(double a) {
  gmath_pair r;
  double ah, al;
  double p = a * a;
  gmath_split(a, &ah, &al);
  r.hi = p;
  r.lo = ((ah * ah - p) + 2.0 * (ah * al)) + al * al;
  return r;
}

/* A small integer (|k| < 2^31) as a double, exactly, with no integer to double
 * conversion (which an i686 build would do through the x87 stack for 64-bit
 * operands): 1.5 * 2^52 + k has the bit pattern 0x4338000000000000 + k. */
static inline double gmath_small_int(int64_t k) {
  return gmath_double(0x4338000000000000ull + (uint64_t)k) - 0x1.8p52;
}

/* A NaN result.  The argument may be a signalling NaN, which x - x quiets and
 * signals invalid for, as C99 Annex F wants; the value returned is the same on
 * every target. */
static inline double gmath_nan_of(double x) {
  volatile double t = x - x;
  (void)t;
  return gmath_double(GMATH_QNAN_BITS);
}

/* NaN with the invalid exception, for an invalid operation on non-NaN inputs. */
static inline double gmath_invalid(void) {
  volatile double z = 0.0;
  volatile double t = z / z;
  (void)t;
  return gmath_double(GMATH_QNAN_BITS);
}

/* +-infinity with the divide-by-zero exception (a finite nonzero over zero). */
static inline double gmath_div_by_zero(uint64_t sign) {
  volatile double z = 0.0;
  volatile double t = 1.0 / z;
  (void)t;
  return gmath_double(GMATH_INF_BITS | sign);
}

/* +-infinity with the overflow and inexact exceptions. */
static inline double gmath_overflow(uint64_t sign) {
  volatile double big = 0x1.fffffffffffffp1023;
  volatile double t = big * big;
  (void)t;
  return gmath_double(GMATH_INF_BITS | sign);
}

/* +-0 with the underflow and inexact exceptions. */
static inline double gmath_underflow(uint64_t sign) {
  volatile double tiny = 0x1p-1022;
  volatile double t = tiny * tiny;
  (void)t;
  return gmath_double(sign);
}

#endif /* GHOTI_IO_GMATH_ELEM_COMMON_H */
