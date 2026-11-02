/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Independently derived inverse hyperbolic functions with DD reductions.
 */
#include <ghoti.io/math/elementary.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include "inverse_hyperbolic_coeff.h"
#include <float.h>

GMATH_STATIC_ASSERT(FLT_RADIX==2 && DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 &&
    DBL_MIN_EXP==-1021 && sizeof(double)==8 && FLT_MANT_DIG==24 &&
    FLT_MAX_EXP==128 && FLT_MIN_EXP==-125 && sizeof(float)==4,
    "inverse hyperbolic functions require IEEE binary64 and binary32");

static gmath_pair ih_add(gmath_pair a,gmath_pair b) {
  gmath_pair s=gmath_two_sum(a.hi,b.hi);
  return gmath_two_sum(s.hi,(s.lo+a.lo)+b.lo);
}
static gmath_pair ih_neg(gmath_pair a) {gmath_pair r={-a.hi,-a.lo};return r;}
static gmath_pair ih_mul(gmath_pair a,gmath_pair b) {
  gmath_pair p=gmath_two_prod(a.hi,b.hi);
  return gmath_two_sum(p.hi,(p.lo+a.hi*b.lo)+a.lo*b.hi);
}
static gmath_pair ih_div(gmath_pair a,gmath_pair b) {
  gmath_pair q={a.hi/b.hi,0.0};
  gmath_pair residual=ih_add(a,ih_neg(ih_mul(b,q)));
  return gmath_two_sum(q.hi,(residual.hi+residual.lo)/b.hi);
}
static gmath_pair ih_times(gmath_pair a,double factor) {
  gmath_pair r={a.hi*factor,a.lo*factor};return r;
}
static gmath_pair ih_sqrt(gmath_pair a) {
  double s=gmath_sqrt(a.hi);gmath_pair root={s,0.0};
  gmath_pair residual=ih_add(a,ih_neg(ih_mul(root,root)));
  return gmath_two_sum(s,(residual.hi+residual.lo)/(2.0*s));
}
static gmath_pair ih_log_series(gmath_pair z) {
  gmath_pair square=ih_mul(z,z),p=ih_log_coeff[39];
  for(int n=38;n>=0;--n)p=ih_add(ih_mul(p,square),ih_log_coeff[n]);
  return ih_times(ih_mul(z,p),2.0);
}
/* All general logarithm arguments exceed1.5. Exact huge arguments have lo=0;
 * normalization never multiplies by a subnormal reciprocal power of two.
 */
static gmath_pair ih_log_pair(gmath_pair y) {
  uint64_t bits=gmath_bits(y.hi);int exponent=(int)(bits>>52)-1023;
  double m=gmath_double((bits&UINT64_C(0x000fffffffffffff))|UINT64_C(0x3ff0000000000000));
  gmath_pair numerator={m-1.0,0.0},ed={gmath_small_int(exponent),0.0};
  gmath_pair value=ih_log_series(ih_div(numerator,gmath_two_sum(m,1.0)));
  value=ih_add(ih_mul(ed,ih_ln2),value);
  if(y.lo!=0.0){gmath_pair correction={y.lo/y.hi,0.0};value=ih_add(value,correction);}
  return value;
}
static gmath_pair ih_log1p(gmath_pair u) {
  if(u.hi<=0.5) {
    gmath_pair two={2.0,0.0};return ih_log_series(ih_div(u,ih_add(two,u)));
  }
  gmath_pair one={1.0,0.0};return ih_log_pair(ih_add(one,u));
}
/* Keep the exact low subtraction parts even when their ultimate effect is
 * smaller than the public one-ULP allowance. */
static gmath_pair ih_acosh_offset(double a) {return gmath_two_sum(a,-1.0);}
static gmath_pair ih_atanh_denominator(double a) {return gmath_two_sum(1.0,-a);}
/* kind:0 asinh,1 acosh,2 atanh. Domain/special/tiny dispatch precedes this.
 * Non-huge products stay below2^121; their Dekker splits cannot overflow.
 */
static gmath_pair ih_value(double a,unsigned kind) {
  gmath_pair arg={a,0.0},one={1.0,0.0},two={2.0,0.0};
  if(kind==2) {
    return ih_times(ih_log1p(ih_div(ih_times(arg,2.0),ih_atanh_denominator(a))),0.5);
  }
  /* For a>=2^60 both corrections to log(2a) have absolute size <2^-121. */
  if(a>=0x1p60)return ih_add(ih_log_pair(arg),ih_ln2);
  if(kind==1) {
    gmath_pair t=ih_acosh_offset(a);
    return ih_log1p(ih_add(t,ih_sqrt(ih_mul(t,ih_add(t,two)))));
  }
  gmath_pair square=ih_mul(arg,arg),root=ih_sqrt(ih_add(one,square));
  if(a<=1.0)return ih_log1p(ih_add(arg,ih_div(square,ih_add(one,root))));
  return ih_log_pair(ih_add(arg,root));
}
static void ih_inexact(void) {
  volatile double one=1.0,tiny=0x1p-54;
  volatile double ignored=one+tiny;(void)ignored;
}
static double ih_double(double x,unsigned kind) {
  uint64_t word=gmath_bits(x),a=word&GMATH_ABS_MASK,sign=word&GMATH_SIGN_BIT;
  if(a>GMATH_INF_BITS) {
    if(!(a&UINT64_C(0x0008000000000000)))(void)gmath_invalid();
    return gmath_double(GMATH_QNAN_BITS);
  }
  if(kind==1) {
    if(sign||a<UINT64_C(0x3ff0000000000000))return gmath_invalid();
    if(a==UINT64_C(0x3ff0000000000000))return 0.0;
    if(a==GMATH_INF_BITS)return x;
  } else {
    if(!a)return gmath_double(word);
    if(kind==2&&a>=UINT64_C(0x3ff0000000000000)) {
      if(a==UINT64_C(0x3ff0000000000000))return gmath_div_by_zero(sign);
      return gmath_invalid();
    }
    if(a==GMATH_INF_BITS)return x;
    if(a<UINT64_C(0x3c30000000000000)) {
      if(a<UINT64_C(0x0010000000000000))(void)gmath_underflow(0);
      else ih_inexact();
      return gmath_double(word);
    }
  }
  ih_inexact();gmath_pair result=ih_value(kind==1?x:gmath_double(a),kind);
  return gmath_double(gmath_bits(result.hi+result.lo)|(kind==1?0:sign));
}
static uint32_t ih_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float ih_float_of(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static float ih_float(float x,unsigned kind) {
  uint32_t word=ih_fbits(x),a=word&UINT32_C(0x7fffffff),sign=word&UINT32_C(0x80000000);
  if(a>UINT32_C(0x7f800000)) {
    if(!(a&UINT32_C(0x00400000)))(void)gmath_invalid();
    return ih_float_of(UINT32_C(0x7fc00000));
  }
  if(kind==1) {
    if(sign||a<UINT32_C(0x3f800000)) {
      (void)gmath_invalid();return ih_float_of(UINT32_C(0x7fc00000));
    }
    if(a==UINT32_C(0x3f800000))return 0.0f;
    if(a==UINT32_C(0x7f800000))return x;
  } else {
    if(!a)return ih_float_of(word);
    if(kind==2&&a>=UINT32_C(0x3f800000)) {
      if(a==UINT32_C(0x3f800000)) {
        (void)gmath_div_by_zero(0);return ih_float_of(sign|UINT32_C(0x7f800000));
      }
      (void)gmath_invalid();return ih_float_of(UINT32_C(0x7fc00000));
    }
    if(a==UINT32_C(0x7f800000))return x;
    if(a<UINT32_C(0x32800000)) {
      if(a<UINT32_C(0x00800000))(void)gmath_underflow(0);
      else ih_inexact();
      return ih_float_of(word);
    }
  }
  ih_inexact();gmath_pair result=ih_value((double)ih_float_of(a),kind);
  return ih_float_of(ih_fbits((float)(result.hi+result.lo))|(kind==1?0:sign));
}
double gmath_asinh(double x){return ih_double(x,0);}
double gmath_acosh(double x){return ih_double(x,1);}
double gmath_atanh(double x){return ih_double(x,2);}
float gmath_asinhf(float x){return ih_float(x,0);}
float gmath_acoshf(float x){return ih_float(x,1);}
float gmath_atanhf(float x){return ih_float(x,2);}
