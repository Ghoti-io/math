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
 * @file Float cube root with conservative result-preserving seed admission.
 * The old Double kernel remains the fallback. See documentation/design.md.
 */
#include "elem_common.h"
#include <ghoti.io/math/elementary.h>
#include <float.h>
#include "cbrt_table.h"
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
/* Identical midpoint expression to the unchanged Double kernel. */
static inline double fc_seed(uint32_t sig,int r) {
  uint64_t fraction=(uint64_t)(sig&0x007fffffu)<<29;
  unsigned j=(sig&0x007fffffu)>>17;
  double m=gmath_double(UINT64_C(0x3ff0000000000000)|fraction);
  double midpoint=1.0+(double)(2*j+1)*0x1p-7;
  double s=(m-midpoint)*gmath_cbrt_seed[j][0];
  double polynomial=1.0+s*(1.0/3.0+s*(-1.0/9.0+s*(5.0/81.0)));
  return (gmath_cbrt_seed[j][1]*polynomial)*gmath_cbrt_factor[r];
}
/* Performance-only prefilter for non-power exact dyadic cubes. For each odd
 * n=3..255, normalize n^3 to a 24-bit significand and mark its top12 fraction
 * bits. False positives merely use the old kernel; correctness does not rely
 * on this mask. tools/oracle/check_cbrtf_fast_budget.py reconstructs all bits.
 */
static const uint64_t fc_cube_mask[64]={
  UINT64_C(0x0082000000000000),UINT64_C(0x0000400100000000),UINT64_C(0x0000100000000020),UINT64_C(0x0000040000080008),
  UINT64_C(0x0000044400000000),UINT64_C(0x0008020000000000),UINT64_C(0x0000020000001000),UINT64_C(0x0004040000000010),
  UINT64_C(0x0000100000400000),UINT64_C(0x0000420008000000),UINT64_C(0x2002000000000000),UINT64_C(0x0010000000000020),
  UINT64_C(0x0102000000080000),UINT64_C(0x2000020000000000),UINT64_C(0x0000000040000000),UINT64_C(0x0000000000000005),
  UINT64_C(0x0000000001001100),UINT64_C(0x2002000000008000),UINT64_C(0x0000000000400000),UINT64_C(0x0000800040001000),
  UINT64_C(0x000000c000000000),UINT64_C(0x0001000800000000),UINT64_C(0x0200000000000008),UINT64_C(0x0000000101000000),
  UINT64_C(0x8000000000000010),UINT64_C(0x0000000000008000),UINT64_C(0x0000000048000000),UINT64_C(0x8000008000000100),
  UINT64_C(0x0010000000000000),UINT64_C(0x0000000100000004),UINT64_C(0x4000000000000004),UINT64_C(0x0000000000020008),
  UINT64_C(0x1000008100000000),UINT64_C(0x0001000000000000),UINT64_C(0x0800000000001000),UINT64_C(0x0002000000000001),
  UINT64_C(0x1000000000040000),UINT64_C(0x0000001001000000),UINT64_C(0x8040000000000000),UINT64_C(0x0000000000000002),
  UINT64_C(0x0000040000000200),UINT64_C(0x0000000040000010),UINT64_C(0x0004000000100000),UINT64_C(0x0000000000000800),
  UINT64_C(0x0000000000000101),UINT64_C(0x0000100040080000),UINT64_C(0x0020000000000000),UINT64_C(0x0000000024000000),
  UINT64_C(0x0000000000001000),UINT64_C(0x0000022000000200),UINT64_C(0x4200000000000000),UINT64_C(0x0040000000000000),
  UINT64_C(0x0000040000800000),UINT64_C(0x0004000000000000),UINT64_C(0x0000000010000040),UINT64_C(0x0000000000002000),
  UINT64_C(0x0000020000808000),UINT64_C(0x0000000000000000),UINT64_C(0x0000040000000030),UINT64_C(0x0400000800000000),
  UINT64_C(0x0000000000000000),UINT64_C(0x0002000000000003),UINT64_C(0x0000000100000000),UINT64_C(0x0000020000400000)
};
static void fc_ix(void) {
  volatile double big=0x1p100;
  volatile double ignored=big+1.0;
  (void)ignored;
}
float gmath_cbrtf(float x) {
  uint32_t word=fc_word(x), a=word&0x7fffffffu;
  if (a>0x7f800000u) {if (!(a&0x00400000u)) (void)gmath_invalid();return fc_value(0x7fc00000u);}
  if (!a||a==0x7f800000u) return fc_value(word);
  /* Preserve the previous subnormal path; seed setup costs more here. */
  if (a<0x00800000u) {
    float result=(float)gmath_cbrt((double)x);
    if (!fc_exact_power(a)) fc_ix();
    return result;
  }
  uint32_t fraction=a&0x007fffffu;
  int e=(int)(a>>23)-127;
  if (!fraction&&e%3==0) return fc_value((word&0x80000000u)|((uint32_t)(e/3+127)<<23));
  float result;
  unsigned index=fraction>>11;
  if (fraction&&((fc_cube_mask[index>>6]>>(index&63u))&1u)) result=(float)gmath_cbrt((double)x);
  else {
    int q=e/3,r=e-3*q;if (r<0) {r+=3;--q;}
    double seed=fc_seed(0x00800000u|fraction,r);uint64_t bits=gmath_bits(seed);
    /* Thresholds repeat every half Float ULP: grid points and midpoints.
     * The actual old Double result is within2^-29 of this normalized seed in
     * every mode. Reject the 2^23-word band at either end, plus binade edges.
     */
    uint64_t residue=bits&UINT64_C(0x0fffffff);
    if (bits>=UINT64_C(0x3ff0000000000000)&&bits<UINT64_C(0x4000000000000000)&&
        residue>UINT64_C(0x00800000)&&residue<UINT64_C(0x0f800000)) {
      double scaled=gmath_double((bits+((uint64_t)(int64_t)q<<52))|((uint64_t)(word&0x80000000u)<<32));
      result=(float)scaled;
    } else result=(float)gmath_cbrt((double)x);
  }
  fc_ix();return result;
}
