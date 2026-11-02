/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Independently derived hyperbolic functions using compensated exp reduction.
 */
#include <ghoti.io/math/elementary.h>
#include "elem_common.h"
#include "hyperbolic_coeff.h"
#include <float.h>

GMATH_STATIC_ASSERT(FLT_RADIX==2 && DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 &&
    DBL_MIN_EXP==-1021 && sizeof(double)==8 && FLT_MANT_DIG==24 &&
    FLT_MAX_EXP==128 && FLT_MIN_EXP==-125 && sizeof(float)==4,
    "hyperbolic functions require IEEE binary64 and binary32");

static gmath_pair hy_add(gmath_pair a,gmath_pair b) {
  gmath_pair s=gmath_two_sum(a.hi,b.hi);
  return gmath_two_sum(s.hi,(s.lo+a.lo)+b.lo);
}
static gmath_pair hy_neg(gmath_pair a) {gmath_pair r={-a.hi,-a.lo};return r;}
static gmath_pair hy_mul(gmath_pair a,gmath_pair b) {
  gmath_pair p=gmath_two_prod(a.hi,b.hi);
  return gmath_two_sum(p.hi,(p.lo+a.hi*b.lo)+a.lo*b.hi);
}
static gmath_pair hy_div(gmath_pair a,gmath_pair b) {
  gmath_pair q={a.hi/b.hi,0.0};
  gmath_pair residual=hy_add(a,hy_neg(hy_mul(b,q)));
  return gmath_two_sum(q.hi,(residual.hi+residual.lo)/b.hi);
}
static gmath_pair hy_times(gmath_pair a,double factor) {
  gmath_pair r={a.hi*factor,a.lo*factor};return r;
}
/* Scaling is exact on the admitted normal ranges. At the upper hyperbolic
 * boundary reduction may choose n=1025, even though exp(a)/2 is finite.
 * No reconstructed large operand is passed to Dekker splitting.
 */
static gmath_pair hy_scale(gmath_pair a,int exponent) {
  if(exponent==1024)return hy_times(hy_times(a,0x1p1023),2.0);
  return hy_times(a,gmath_double((uint64_t)(exponent+1023)<<52));
}
static gmath_pair hy_exp_series(gmath_pair r) {
  gmath_pair p=hy_exp_coeff[24];
  for(int n=23;n>=0;--n)p=hy_add(hy_mul(p,r),hy_exp_coeff[n]);
  return hy_mul(r,p);
}
/* half=1 computes exp(a)/2 directly, without forming overflowing exp(a). */
static gmath_pair hy_exp(double a,int half,int minus_one) {
  double estimate=a*0x1.71547652b82fep+0;
  int exponent=(int)(estimate+0.5);
  gmath_pair ed={gmath_small_int(exponent),0.0},arg={a,0.0},one={1.0,0.0};
  gmath_pair r=hy_add(arg,hy_neg(hy_mul(ed,hy_ln2)));
  gmath_pair value=hy_exp_series(r);
  if(minus_one && !exponent)return value;
  value=hy_scale(hy_add(one,value),exponent-half);
  return minus_one?hy_add(value,hy_neg(one)):value;
}
/* kind: 0 sinh, 1 cosh, 2 tanh. All split operands stay below exp(40),
 * except the final exact scaling/addition of a half-exponential.
 */
static gmath_pair hy_value(double a,unsigned kind) {
  gmath_pair one={1.0,0.0};
  if(kind==2) {
    gmath_pair t=hy_exp(2.0*a,0,1),two={2.0,0.0};
    return hy_div(t,hy_add(t,two));
  }
  if(a<=0.5) {
    gmath_pair t=hy_exp(a,0,1),denominator=hy_add(one,t);
    if(kind==0)return hy_times(hy_add(t,hy_div(t,denominator)),0.5);
    return hy_add(one,hy_times(hy_div(hy_mul(t,t),denominator),0.5));
  }
  if(a>=40.0)return hy_exp(a,1,0);
  gmath_pair value=hy_exp(a,0,0),reciprocal=hy_div(one,value);
  return hy_times(hy_add(value,kind==0?hy_neg(reciprocal):reciprocal),0.5);
}
static void hy_inexact(void) {
  volatile double one=1.0,tiny=0x1p-54;
  volatile double ignored=one+tiny;(void)ignored;
}
static double hy_double(double x,unsigned kind) {
  uint64_t word=gmath_bits(x),a=word&GMATH_ABS_MASK,sign=kind==1?0:word&GMATH_SIGN_BIT;
  if(a>GMATH_INF_BITS) {
    if(!(a&UINT64_C(0x0008000000000000)))(void)gmath_invalid();
    return gmath_double(GMATH_QNAN_BITS);
  }
  if(!a)return kind==1?1.0:gmath_double(word);
  if(a==GMATH_INF_BITS)return kind==2?gmath_double(sign|UINT64_C(0x3ff0000000000000)):gmath_double(sign|a);
  if(kind!=2 && a>=UINT64_C(0x408633ce8fb9f87e))return gmath_overflow(sign);
  if(a<UINT64_C(0x3c30000000000000)) {
    if(kind!=1 && a<UINT64_C(0x0010000000000000))(void)gmath_underflow(0);
    else hy_inexact();
    return kind==1?1.0:gmath_double(word);
  }
  hy_inexact();
  if(kind==2 && a>=UINT64_C(0x4034000000000000))return gmath_double(sign|UINT64_C(0x3ff0000000000000));
  gmath_pair result=hy_value(gmath_double(a),kind);
  return gmath_double(gmath_bits(result.hi+result.lo)|sign);
}
static uint32_t hy_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float hy_float_of(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static float hy_float(float x,unsigned kind) {
  uint32_t word=hy_fbits(x),a=word&UINT32_C(0x7fffffff),sign=kind==1?0:word&UINT32_C(0x80000000);
  if(a>UINT32_C(0x7f800000)) {
    if(!(a&UINT32_C(0x00400000)))(void)gmath_invalid();
    return hy_float_of(UINT32_C(0x7fc00000));
  }
  if(!a)return kind==1?1.0f:hy_float_of(word);
  if(a==UINT32_C(0x7f800000))return hy_float_of(sign|(kind==2?UINT32_C(0x3f800000):a));
  if(kind!=2 && a>=UINT32_C(0x42b2d4fd)) {
    (void)gmath_overflow(0);return hy_float_of(sign|UINT32_C(0x7f800000));
  }
  if(a<UINT32_C(0x32800000)) {
    if(kind!=1 && a<UINT32_C(0x00800000))(void)gmath_underflow(0);
    else hy_inexact();
    return kind==1?1.0f:hy_float_of(word);
  }
  hy_inexact();
  if(kind==2 && a>=UINT32_C(0x41200000))return hy_float_of(sign|UINT32_C(0x3f800000));
  gmath_pair result=hy_value((double)hy_float_of(a),kind);
  return hy_float_of(hy_fbits((float)(result.hi+result.lo))|sign);
}
double gmath_sinh(double x){return hy_double(x,0);}
double gmath_cosh(double x){return hy_double(x,1);}
double gmath_tanh(double x){return hy_double(x,2);}
float gmath_sinhf(float x){return hy_float(x,0);}
float gmath_coshf(float x){return hy_float(x,1);}
float gmath_tanhf(float x){return hy_float(x,2);}
