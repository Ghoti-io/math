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

/** @file Private binary32 reduction and conservative rounding-cell gate. */
#ifndef GHOTI_IO_GMATH_FLOATTRIG_REDUCE_H
#define GHOTI_IO_GMATH_FLOATTRIG_REDUCE_H

#include <ghoti.io/math/macros.h>
#include "elem_common.h"
#include "floattrig_reduce_table.h"

/* a is the positive raw word of a finite binary32 argument greater than 1.
 * C[e] approximates ((2/pi)*2^(e-23)) modulo 4 with 80 fractional bits.
 * Multiplication by the 24-bit significand leaves absolute phase error <2^-56.
 * This integer phase calculation cannot introduce floating exceptions. */
static inline int floattrig_reduce(uint32_t a, unsigned * quadrant, double * r) {
  unsigned e = (a >> 23) - 127u;
  uint32_t m = (a & 0x007fffffu) | 0x00800000u;
  const uint32_t * c = floattrig_reduce_table[e];
  uint64_t v = (uint64_t)m * c[0];
  uint32_t f0 = (uint32_t)v;
  v = (uint64_t)m * c[1] + (v >> 32);
  uint32_t f1 = (uint32_t)v;
  v = (uint64_t)m * c[2] + (v >> 32);
  uint32_t f2 = (uint32_t)v & 0xffffu;
  unsigned up = f2 >> 15;
  *quadrant = ((unsigned)(v >> 16) + up) & 3u;

  /* Magnitude of the signed fractional part, complemented within 80 bits. */
  uint32_t mask = 0u - up;
  v = (uint64_t)(f0 ^ mask) + up;
  f0 = (uint32_t)v;
  v = (uint64_t)(f1 ^ mask) + (v >> 32);
  f1 = (uint32_t)v;
  f2 = ((f2 ^ mask) + (uint32_t)(v >> 32)) & 0xffffu;
  if (f2 < 16u) {
    return 0; /* |phase|<2^-12: preserve the double pole/tiny-result path. */
  }

  /* Top 53 bits, truncated toward zero. No integer-to-double conversion and
   * no host byte-order assumptions. f2 is nonzero here. */
#if (defined(__GNUC__) || defined(__clang__)) && !defined(GMATH_FLOATTRIG_PORTABLE_BITS)
  unsigned leading = 63u - (unsigned)__builtin_clzll((unsigned long long)f2);
#else
  unsigned leading = 0;
  uint32_t scan = f2;
  while ((scan >>= 1) != 0) {
    ++leading;
  }
#endif
  unsigned shift = leading + 12u;
  uint64_t low = ((uint64_t)f1 << 32) | f0;
  uint64_t significand = (low >> shift) | ((uint64_t)f2 << (64u - shift));
  double fraction = gmath_double(((uint64_t)(1023u + leading - 16u) << 52) |
      (significand & 0x000fffffffffffffull));
  double reduced = fraction * 0x1.921fb54442d18p0;
  *r = gmath_double(gmath_bits(reduced) | ((uint64_t)up << 63));
  return 1;
}

/* The reduction and bounded Taylor estimates have relative error <2^-36 on
 * the admitted interval. 2^-34 also reserves ample room for the existing
 * double kernel's error. Accept only if that entire interval stays inside
 * one binary32 nearest rounding cell. Uncertain cases use the old path.
 * Estimates are normal and bounded away from both float under/overflow. */
static inline int floattrig_accept(double y, float * result) {
  float candidate = (float)y;
  uint32_t bits;
  memcpy(&bits, &candidate, sizeof bits);
  uint32_t a = bits & 0x7fffffffu;
  float prev, next;
  uint32_t word = a - 1u;
  memcpy(&prev, &word, sizeof prev);
  word = a + 1u;
  memcpy(&next, &word, sizeof next);
  double magnitude = gmath_double(gmath_bits(y) & GMATH_ABS_MASK);
  double centre = (double)(bits & 0x80000000u ? -candidate : candidate);
  double lower = ((double)prev + centre) * 0.5;
  double upper = (centre + (double)next) * 0.5;
  double bound = magnitude * 0x1p-34;
  if (magnitude - lower > bound && upper - magnitude > bound) {
    *result = candidate;
    return 1;
  }
  return 0;
}

#endif /* GHOTI_IO_GMATH_FLOATTRIG_REDUCE_H */
