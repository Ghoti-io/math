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

/** @file Shared inverse sine/cosine series and half-angle reduction.
 * Independently derived from the binomial series of (1-x*x)^(-1/2),
 * integrated term by term. No other math implementation is used.
 */
#include <ghoti.io/math/elementary.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include "inverse_trig_coeff.h"
#include <float.h>

GMATH_STATIC_ASSERT(FLT_RADIX == 2 && DBL_MANT_DIG == 53 &&
    DBL_MAX_EXP == 1024 && DBL_MIN_EXP == -1021 && sizeof(double) == 8 &&
    FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128 && FLT_MIN_EXP == -125 &&
    sizeof(float) == 4, "inverse trig requires IEEE binary64 and binary32");

static const gmath_pair inverse_pio2 = {0x1.921fb54442d18p+0, 0x1.1a62633145c07p-54};

static gmath_pair inverse_add(gmath_pair a, gmath_pair b) {
  gmath_pair s = gmath_two_sum(a.hi, b.hi);
  return gmath_two_sum(s.hi, (s.lo + a.lo) + b.lo);
}

static gmath_pair inverse_mul(gmath_pair a, gmath_pair b) {
  gmath_pair p = gmath_two_prod(a.hi, b.hi);
  return gmath_two_sum(p.hi, (p.lo + a.hi*b.lo) + a.lo*b.hi);
}

static gmath_pair inverse_scale(gmath_pair a, double scale) {
  gmath_pair r = {a.hi*scale, a.lo*scale};
  return r;
}

/* 33 positive terms, |x|<=1/2. The omitted tail relative to x is
 * <= c_33 * (1/4)^33 / (1-1/4) < 2^-74. Split coefficients and
 * compensated Horner arithmetic retain a reserve below binary64 rounding.
 * This is an approximation, not a claim of all-input correct rounding.
 */
static gmath_pair inverse_small(double x) {
  gmath_pair square = gmath_two_sqr(x), p = inverse_asin_coeff[32];
  for (int n=31; n>=0; --n) {
    p = inverse_add(inverse_mul(p, square), inverse_asin_coeff[n]);
  }
  gmath_pair arg = {x, 0.0};
  return inverse_mul(arg, p);
}

/* For 1/2<a<1, z=(1-a)/2 is exact by Sterbenz and power-of-two
 * scaling. Keep the root's rounding residual rather than propagating a
 * rounded root through the endpoint-sensitive inverse function.
 */
static gmath_pair inverse_half(double a) {
  double z = (1.0-a)*0.5, root = gmath_sqrt(z);
  gmath_pair square = gmath_two_sqr(root);
  double residual = (z-square.hi)-square.lo;
  double correction = (residual/(2.0*root))/gmath_sqrt(1.0-z);
  gmath_pair result = inverse_small(root), delta = {correction, 0.0};
  return inverse_scale(inverse_add(result, delta), 2.0);
}

/* a is positive, finite, and outside the tiny/endpoint guards. */
static gmath_pair inverse_angle(double a, int negative, int cosine) {
  gmath_pair result;
  if (a<=0.5) {
    result = inverse_small(a);
    if (cosine) result = inverse_add(inverse_pio2,
        inverse_scale(result, negative ? 1.0 : -1.0));
  } else {
    result = inverse_half(a);
    if (!cosine) result = inverse_add(inverse_pio2, inverse_scale(result,-1.0));
    else if (negative) result = inverse_add(inverse_scale(inverse_pio2,2.0),
        inverse_scale(result,-1.0));
  }
  return !cosine && negative ? inverse_scale(result,-1.0) : result;
}

static void inverse_inexact(void) {
  volatile double one=1.0, tiny=0x1p-54;
  volatile double ignored=one+tiny;
  (void)ignored;
}

static double inverse_double(double x, int cosine) {
  uint64_t word=gmath_bits(x), a=word&GMATH_ABS_MASK;
  int negative=(word&GMATH_SIGN_BIT)!=0;
  if (a>GMATH_INF_BITS) {
    if (!(a&UINT64_C(0x0008000000000000))) (void)gmath_invalid();
    return gmath_double(GMATH_QNAN_BITS);
  }
  if (a>UINT64_C(0x3ff0000000000000)) return gmath_invalid();
  if (!cosine && !a) return gmath_double(word);
  if (cosine && word==UINT64_C(0x3ff0000000000000)) return 0.0;
  if (!cosine && a<UINT64_C(0x3e10000000000000)) {
    if (a<UINT64_C(0x0010000000000000)) (void)gmath_underflow(0);
    else inverse_inexact();
    return gmath_double(word);
  }
  inverse_inexact();
  if (a==UINT64_C(0x3ff0000000000000)) {
    return gmath_double(cosine ? UINT64_C(0x400921fb54442d18) :
        UINT64_C(0x3ff921fb54442d18)|(word&GMATH_SIGN_BIT));
  }
  if (cosine && a<UINT64_C(0x3c30000000000000)) return inverse_pio2.hi;
  gmath_pair result=inverse_angle(gmath_double(a),negative,cosine);
  return result.hi+result.lo;
}

static uint32_t inverse_float_bits(float x) {
  uint32_t word; memcpy(&word,&x,sizeof word); return word;
}
static float inverse_float_of(uint32_t word) {
  float x; memcpy(&x,&word,sizeof x); return x;
}

static float inverse_float(float x, int cosine) {
  uint32_t word=inverse_float_bits(x), a=word&UINT32_C(0x7fffffff);
  int negative=(word>>31)!=0;
  if (a>UINT32_C(0x7f800000)) {
    if (!(a&UINT32_C(0x00400000))) (void)gmath_invalid();
    return inverse_float_of(UINT32_C(0x7fc00000));
  }
  if (a>UINT32_C(0x3f800000)) {
    (void)gmath_invalid(); return inverse_float_of(UINT32_C(0x7fc00000));
  }
  if (!cosine && !a) return inverse_float_of(word);
  if (cosine && word==UINT32_C(0x3f800000)) return 0.0f;
  if (!cosine && a<UINT32_C(0x39800000)) {
    if (a<UINT32_C(0x00800000)) (void)gmath_underflow(0);
    else inverse_inexact();
    return inverse_float_of(word);
  }
  inverse_inexact();
  if (a==UINT32_C(0x3f800000)) return inverse_float_of(cosine ?
      UINT32_C(0x40490fdb) : UINT32_C(0x3fc90fdb)|(word&UINT32_C(0x80000000)));
  if (cosine && a<UINT32_C(0x31800000)) return inverse_float_of(UINT32_C(0x3fc90fdb));
  gmath_pair result=inverse_angle((double)inverse_float_of(a),negative,cosine);
  return (float)(result.hi+result.lo);
}

double gmath_asin(double x) { return inverse_double(x,0); }
double gmath_acos(double x) { return inverse_double(x,1); }
float gmath_asinf(float x) { return inverse_float(x,0); }
float gmath_acosf(float x) { return inverse_float(x,1); }
