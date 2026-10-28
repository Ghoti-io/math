/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 *
 * Exact nearest-quotient remainder from positional integer division. This is
 * distinct from fmod's quotient truncation; the existing fmod is unchanged.
 * Normalized operands are mx*2^(ex-p), my*2^(ey-p). Retain quotient mod128
 * while reducing (mx*2^(ex-ey)) mod my. Before each shift r<my<2^(p+1),
 * so a chunk of at most63-p bits fits uint64_t, even for extreme exponents.
 * The final comparison2r:my rounds the quotient, with parity resolving ties.
 * The exact residual has at most p+1 significant bits and lies on the input
 * dyadic lattice: encoding even a minimum-subnormal result loses no bits.
 */
#include <ghoti.io/math/basic.h>
#include <float.h>
#include "elem_common.h"
GMATH_STATIC_ASSERT(sizeof(float)==sizeof(uint32_t)&&FLT_RADIX==2&&
                    FLT_MANT_DIG==24&&FLT_MAX_EXP==128,
                    "IEEE remainder requires binary32 Float");
static inline unsigned irq_shift(uint64_t m,unsigned p) {
#if (defined(__GNUC__)||defined(__clang__)) && ULLONG_MAX==UINT64_MAX && !defined(GMATH_IEEE_REMAINDER_PORTABLE_BITS)
  return (unsigned)__builtin_clzll((unsigned long long)m)-(63u-p);
#else
  unsigned n=0;while(m<(UINT64_C(1)<<p)){m<<=1;++n;}return n;
#endif
}
static inline uint64_t irq_significand(uint64_t a,unsigned p,int bias,int *e) {
  unsigned field=(unsigned)(a>>p);uint64_t hidden=UINT64_C(1)<<p;
  uint64_t m=a&(hidden-1);*e=field?(int)field-bias:1-bias;
  if(field)return m|hidden;
  unsigned n=irq_shift(m,p);*e-=(int)n;return m<<n;
}
static inline uint64_t irq_pack(uint64_t r,int e,unsigned p,int bias) {
  if(!r)return 0;
  unsigned n=irq_shift(r,p);r<<=n;e-=(int)n;
  if(e>=1-bias)return ((uint64_t)(e+bias)<<p)|(r&((UINT64_C(1)<<p)-1));
  /* The input lattice ensures all discarded bits are zero and shift<=p. */
  return r>>(unsigned)(1-bias-e);
}
static uint64_t irq_word(uint64_t xb,uint64_t yb,unsigned p,unsigned eb,int bias,int *quo) {
  uint64_t sign_bit=UINT64_C(1)<<(p+eb),sign=xb&sign_bit;
  uint64_t inf=((UINT64_C(1)<<eb)-1)<<p,quiet=UINT64_C(1)<<(p-1);
  uint64_t ax=xb&(sign_bit-1),ay=yb&(sign_bit-1);
  if(quo)*quo=0;
  if(ax>inf||ay>inf) {
    if((ax>inf&&!(ax&quiet))||(ay>inf&&!(ay&quiet)))(void)gmath_invalid();
    return inf|quiet;
  }
  if(ax==inf||!ay){(void)gmath_invalid();return inf|quiet;}
  if(!ax||ay==inf)return xb;
  int ex,ey;uint64_t mx=irq_significand(ax,p,bias,&ex),my=irq_significand(ay,p,bias,&ey);
  int gap=ex-ey,e=ey;uint64_t q,r;
  if(gap<0) {
    if(gap<-1||mx<=my)return xb; /* Includes exact half: quotient0 is even. */
    r=2*my-mx;e=ex;q=1;sign^=sign_bit;
  } else {
    q=mx/my;r=mx%my;
    while(gap>0&&r) {
      unsigned s=gap>(int)(63u-p)?63u-p:(unsigned)gap;
      uint64_t t=r<<s;q=((q<<s)+t/my)&127u;r=t%my;gap-=(int)s;
    }
    /* A zero residual still appends the remaining quotient zero bits. */
    if(gap>0)q=gap>=7?0:(q<<(unsigned)gap)&127u;
    if(2*r>my||(2*r==my&&(q&1u))) {r=my-r;q=(q+1u)&127u;sign^=sign_bit;}
  }
  if(quo)*quo=((xb^yb)&sign_bit)?-(int)q:(int)q;
  return sign|irq_pack(r,e,p,bias);
}
double gmath_remquo(double x,double y,int *quo) {
  return gmath_double(irq_word(gmath_bits(x),gmath_bits(y),52,11,1023,quo));
}
double gmath_remainder(double x,double y) {return gmath_remquo(x,y,NULL);}
float gmath_remquof(float x,float y,int *quo) {
  uint32_t xb,yb;memcpy(&xb,&x,sizeof xb);memcpy(&yb,&y,sizeof yb);
  uint32_t bits=(uint32_t)irq_word(xb,yb,23,8,127,quo);
  float result;memcpy(&result,&bits,sizeof result);return result;
}
float gmath_remainderf(float x,float y) {return gmath_remquof(x,y,NULL);}
