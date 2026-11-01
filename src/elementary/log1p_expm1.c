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

/** @file Cancellation-safe logarithm/exponential family.
 * Independently derived from log(1+x)=2*atanh(x/(2+x)) and the exponential
 * Taylor series, with ln2 reduction. Existing exp/log kernels stay unchanged.
 */
#include <ghoti.io/math/elementary.h>
#include "elem_common.h"
#include "log1p_expm1_coeff.h"
#include <float.h>

GMATH_STATIC_ASSERT(FLT_RADIX==2 && DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 &&
    DBL_MIN_EXP==-1021 && sizeof(double)==8 && FLT_MANT_DIG==24 &&
    FLT_MAX_EXP==128 && FLT_MIN_EXP==-125 && sizeof(float)==4,
    "log1p/expm1 requires IEEE binary64 and binary32");

static gmath_pair plus_add(gmath_pair a,gmath_pair b) {
  gmath_pair s=gmath_two_sum(a.hi,b.hi);
  return gmath_two_sum(s.hi,(s.lo+a.lo)+b.lo);
}
static gmath_pair plus_neg(gmath_pair a) {
  gmath_pair r={-a.hi,-a.lo};return r;
}
static gmath_pair plus_mul(gmath_pair a,gmath_pair b) {
  gmath_pair p=gmath_two_prod(a.hi,b.hi);
  return gmath_two_sum(p.hi,(p.lo+a.hi*b.lo)+a.lo*b.hi);
}
static gmath_pair plus_div(gmath_pair a,gmath_pair b) {
  gmath_pair q={a.hi/b.hi,0.0};
  gmath_pair residual=plus_add(a,plus_neg(plus_mul(b,q)));
  return gmath_two_sum(q.hi,(residual.hi+residual.lo)/b.hi);
}
static gmath_pair plus_times(gmath_pair a,double factor) {
  gmath_pair r={a.hi*factor,a.lo*factor};return r;
}
static double plus_power(int exponent) {
  return gmath_double((uint64_t)(exponent+1023)<<52);
}

/* 2*atanh(z), |z|<=1/3. Forty positive odd terms leave a relative
 * truncation tail below2^-132. DD coefficients/operations have their own
 * rounding errors; this tail inequality is not a correct-rounding proof.
 */
static gmath_pair plus_log_series(gmath_pair z) {
  gmath_pair square=plus_mul(z,z),p=plus_log_coeff[39];
  for(int n=38;n>=0;--n)p=plus_add(plus_mul(p,square),plus_log_coeff[n]);
  return plus_times(plus_mul(z,p),2.0);
}
static gmath_pair plus_log(double x) {
  if(x>=-0.5 && x<=0.5) {
    gmath_pair arg={x,0.0};
    return plus_log_series(plus_div(arg,gmath_two_sum(2.0,x)));
  }
  /* For x>=2^60, omitting +1 costs <2^-60 in log, below2^-13 ULP.
   * Never form 1+DBL_MAX or a tiny reciprocal/correction on this path.
   */
  gmath_pair sum={x,0.0};
  if(x<0x1p60)sum=gmath_two_sum(1.0,x);
  uint64_t bits=gmath_bits(sum.hi);int exponent=(int)(bits>>52)-1023;
  double m=gmath_double((bits&UINT64_C(0x000fffffffffffff))|UINT64_C(0x3ff0000000000000));
  gmath_pair numerator={m-1.0,0.0};
  gmath_pair value=plus_log_series(plus_div(numerator,gmath_two_sum(m,1.0)));
  gmath_pair ed={gmath_small_int(exponent),0.0};
  value=plus_add(plus_mul(ed,plus_ln2),value);
  if(sum.lo!=0.0) {
    gmath_pair correction={sum.lo/sum.hi,0.0};
    value=plus_add(value,correction);
  }
  return value;
}

/* expm1(r) on |r|<=~ln2/2. Twenty-five Taylor terms leave ample
 * reserve below binary64 rounding; r itself is a compensated pair.
 */
static gmath_pair plus_exp_series(gmath_pair r) {
  gmath_pair p=plus_exp_coeff[24];
  for(int n=23;n>=0;--n)p=plus_add(plus_mul(p,r),plus_exp_coeff[n]);
  return plus_mul(r,p);
}
static gmath_pair plus_exp(double x) {
  double estimate=x*0x1.71547652b82fep+0;
  int exponent=(int)(estimate+(estimate>=0.0?0.5:-0.5));
  gmath_pair ed={gmath_small_int(exponent),0.0},arg={x,0.0};
  gmath_pair r=plus_add(arg,plus_neg(plus_mul(ed,plus_ln2)));
  gmath_pair value=plus_exp_series(r);
  if(!exponent)return value;
  gmath_pair one={1.0,0.0};value=plus_add(one,value);
  /* Scaling by powers of two is exact in these bounded normal ranges.
   * Do not use Dekker splitting/products on reconstructed huge operands.
   */
  if(exponent==1024)value=plus_times(plus_times(value,0x1p1023),2.0);
  else value=plus_times(value,plus_power(exponent));
  gmath_pair minus_one={-1.0,0.0};return plus_add(value,minus_one);
}
static void plus_inexact(void) {
  volatile double one=1.0,tiny=0x1p-54;
  volatile double ignored=one+tiny;(void)ignored;
}
static double plus_double(double x,int exponential) {
  uint64_t word=gmath_bits(x),a=word&GMATH_ABS_MASK;
  if(a>GMATH_INF_BITS) {
    if(!(a&UINT64_C(0x0008000000000000)))(void)gmath_invalid();
    return gmath_double(GMATH_QNAN_BITS);
  }
  if(!a)return gmath_double(word);
  if(exponential) {
    if(a==GMATH_INF_BITS)return word&GMATH_SIGN_BIT?-1.0:x;
    if(x>=gmath_double(UINT64_C(0x40862e42fefa39f0)))return gmath_overflow(0);
    if(x<=-40.0){plus_inexact();return -1.0;}
  } else {
    if(word==UINT64_C(0xbff0000000000000))return gmath_div_by_zero(GMATH_SIGN_BIT);
    if((word&GMATH_SIGN_BIT)&&a>UINT64_C(0x3ff0000000000000))return gmath_invalid();
    if(a==GMATH_INF_BITS)return x;
  }
  if(a<UINT64_C(0x3c30000000000000)) {
    if(a<UINT64_C(0x0010000000000000))(void)gmath_underflow(0);
    else plus_inexact();
    return gmath_double(word);
  }
  plus_inexact();gmath_pair result=exponential?plus_exp(x):plus_log(x);
  return result.hi+result.lo;
}
static uint32_t plus_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float plus_float_of(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static float plus_float(float x,int exponential) {
  uint32_t word=plus_fbits(x),a=word&UINT32_C(0x7fffffff);
  if(a>UINT32_C(0x7f800000)) {
    if(!(a&UINT32_C(0x00400000)))(void)gmath_invalid();
    return plus_float_of(UINT32_C(0x7fc00000));
  }
  if(!a)return plus_float_of(word);
  if(exponential) {
    if(a==UINT32_C(0x7f800000))return word&UINT32_C(0x80000000)?-1.0f:x;
    if(!(word&UINT32_C(0x80000000))&&a>=UINT32_C(0x42b17218)) {
      (void)gmath_overflow(0);return plus_float_of(UINT32_C(0x7f800000));
    }
    if(x<=-20.0f){plus_inexact();return -1.0f;}
  } else {
    if(word==UINT32_C(0xbf800000)) {
      (void)gmath_div_by_zero(GMATH_SIGN_BIT);return plus_float_of(UINT32_C(0xff800000));
    }
    if((word&UINT32_C(0x80000000))&&a>UINT32_C(0x3f800000)) {
      (void)gmath_invalid();return plus_float_of(UINT32_C(0x7fc00000));
    }
    if(a==UINT32_C(0x7f800000))return x;
  }
  if(a<UINT32_C(0x32800000)) {
    if(a<UINT32_C(0x00800000))(void)gmath_underflow(0);
    else plus_inexact();
    return plus_float_of(word);
  }
  plus_inexact();gmath_pair result=exponential?plus_exp((double)x):plus_log((double)x);
  return (float)(result.hi+result.lo);
}
double gmath_log1p(double x){return plus_double(x,0);}
double gmath_expm1(double x){return plus_double(x,1);}
float gmath_log1pf(float x){return plus_float(x,0);}
float gmath_expm1f(float x){return plus_float(x,1);}
