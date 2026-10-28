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
 * @file Float cube root through the unchanged own-project Double kernel.
 * Raw special dispatch precedes widening. See documentation/design.md.
 */
#include "elem_common.h"
#include <ghoti.io/math/elementary.h>
#include <float.h>
GMATH_STATIC_ASSERT(sizeof(float)==sizeof(uint32_t) && FLT_RADIX==2 &&
                    FLT_MANT_DIG==24 && FLT_MAX_EXP==128,
                    "Float cube root requires IEEE binary32");
static inline uint32_t fc_word(float x) {
  uint32_t word; memcpy(&word,&x,sizeof word); return word;
}
static inline float fc_value(uint32_t word) {
  float x; memcpy(&x,&word,sizeof x); return x;
}
/* Nonzero finite raw magnitude; exactly representable cube-root binary power. */
static int fc_exact_power(uint32_t a) {
  int exponent;
  if (a>=0x00800000u) {
    if (a&0x007fffffu) return 0;
    exponent=(int)(a>>23)-127;
  } else {
    if (a&(a-1u)) return 0;
    exponent=-149;
    while (a>1u) { a>>=1; ++exponent; }
  }
  return exponent%3==0;
}
float gmath_cbrtf(float x) {
  uint32_t word=fc_word(x), a=word&0x7fffffffu;
  if (a>0x7f800000u) {
    if (!(a&0x00400000u)) (void)gmath_invalid();
    return fc_value(0x7fc00000u);
  }
  if (!a || a==0x7f800000u) return fc_value(word);
  float result=(float)gmath_cbrt((double)x);
  if (!fc_exact_power(a)) {
    volatile double big=0x1p100;
    volatile double ignored=big+1.0;
    (void)ignored;
  }
  return result;
}
