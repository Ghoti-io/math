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
 * Exact binary32 decomposition and power-of-two scaling.
 * See documentation/design.md for the integer proof and exception contract.
 */
#include "elem_common.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/macros.h>
#include <limits.h>

GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                        FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                        FLT_MAX_EXP == 128,
                    "Float scaling requires IEEE binary32");
#define FS_SIGN 0x80000000u
#define FS_ABS 0x7fffffffu
#define FS_INF 0x7f800000u
#define FS_NAN 0x7fc00000u
#define FS_HIDDEN 0x00800000u
#define FS_FRACTION 0x007fffffu

static inline uint32_t fs_word(float fs_x) {
  uint32_t fs_b;
  memcpy(&fs_b, &fs_x, sizeof fs_b);
  return fs_b;
}
static inline float fs_value(uint32_t fs_b) {
  float fs_x;
  memcpy(&fs_x, &fs_b, sizeof fs_x);
  return fs_x;
}
static inline float fs_nan(uint32_t fs_b) {
  if ((fs_b & 0x00400000u) == 0) {
    (void)gmath_invalid();
  }
  return fs_value(FS_NAN);
}
/* Nonzero finite magnitude only; E ranges -22..254 and sig has bit23 set. */
static inline void fs_unpack(uint32_t fs_a, int * fs_e, uint32_t * fs_sig) {
  if (fs_a >= FS_HIDDEN) {
    *fs_e = (int)(fs_a >> 23);
    *fs_sig = FS_HIDDEN | (fs_a & FS_FRACTION);
    return;
  }
  unsigned fs_shift;
#if (defined(__GNUC__) || defined(__clang__)) && UINT_MAX == UINT32_MAX &&     \
    !defined(GMATH_FLOATSCALE_PORTABLE_BITS)
  fs_shift = (unsigned)__builtin_clz(fs_a) - 8u;
#else
  fs_shift = 0;
  while ((fs_a << fs_shift) < FS_HIDDEN) {
    ++fs_shift;
  }
#endif
  *fs_e = 1 - (int)fs_shift;
  *fs_sig = fs_a << fs_shift;
}
static inline void fs_inexact(void) {
  volatile double fs_big = 0x1p100;
  volatile double fs_ignored = fs_big + 1.0;
  (void)fs_ignored;
}
float gmath_frexpf(float x, int * e) {
  uint32_t fs_b = fs_word(x), fs_a = fs_b & FS_ABS;
  if (e != NULL) {
    *e = 0;
  }
  if (fs_a >= FS_INF) {
    return fs_a > FS_INF ? fs_nan(fs_b) : fs_value(fs_b);
  }
  if (fs_a == 0) {
    return fs_value(fs_b);
  }
  int fs_e;
  uint32_t fs_sig;
  fs_unpack(fs_a, &fs_e, &fs_sig);
  if (e != NULL) {
    *e = fs_e - 126;
  }
  return fs_value((fs_b & FS_SIGN) | (126u << 23) | (fs_sig & FS_FRACTION));
}
int gmath_ilogbf(float x) {
  uint32_t fs_a = fs_word(x) & FS_ABS;
  if (fs_a >= FS_INF) {
    (void)gmath_invalid();
    return fs_a > FS_INF ? GMATH_ILOGBNAN : INT_MAX;
  }
  if (fs_a == 0) {
    (void)gmath_invalid();
    return GMATH_ILOGB0;
  }
  int fs_e;
  uint32_t fs_sig;
  fs_unpack(fs_a, &fs_e, &fs_sig);
  return fs_e - 127;
}
float gmath_scalbnf(float x, int n) {
  uint32_t fs_b = fs_word(x), fs_a = fs_b & FS_ABS, fs_sign = fs_b & FS_SIGN;
  if (fs_a >= FS_INF) {
    return fs_a > FS_INF ? fs_nan(fs_b) : fs_value(fs_b);
  }
  if (fs_a == 0) {
    return fs_value(fs_b);
  }
  int fs_e;
  uint32_t fs_sig;
  fs_unpack(fs_a, &fs_e, &fs_sig);
  int fs_k = n > 512 ? 512 : (n < -512 ? -512 : n);
  int fs_ne = fs_e + fs_k;
  if (fs_ne >= 255) {
    (void)gmath_overflow(0);
    return fs_value(fs_sign | FS_INF);
  }
  if (fs_ne >= 1) {
    return fs_value(fs_sign | ((uint32_t)fs_ne << 23) | (fs_sig & FS_FRACTION));
  }
  unsigned fs_shift = (unsigned)(1 - fs_ne);
  if (fs_shift > 24u) {
    (void)gmath_underflow(0);
    return fs_value(fs_sign);
  }
  uint32_t fs_q = fs_sig >> fs_shift;
  uint32_t fs_rem = fs_sig & ((UINT32_C(1) << fs_shift) - 1u);
  uint32_t fs_half = UINT32_C(1) << (fs_shift - 1u);
  if (fs_rem > fs_half || (fs_rem == fs_half && (fs_q & 1u))) {
    ++fs_q;
  }
  if (fs_rem != 0) {
    if (fs_q < FS_HIDDEN) {
      (void)gmath_underflow(0);
    } else {
      fs_inexact();
    }
  }
  return fs_value(fs_sign | fs_q);
}
float gmath_ldexpf(float x, int n) {
  return gmath_scalbnf(x, n);
}
