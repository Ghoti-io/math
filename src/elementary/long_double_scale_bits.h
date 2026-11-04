/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Integer scaling and variable-population double-double neighbors. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_SCALE_BITS_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_SCALE_BITS_H
#include <ghoti.io/math/macros.h>
static void __attribute__((noinline,used)) lds_raise_inexact(void) {
  volatile double a=1.0, b=0x1p-54;
  volatile double result=a+b;
  (void)result;
}
/* These four isolated functions are the only allowed arithmetic regions.
 * noinline keeps flag generation out of every integer numerical decision. */
static void __attribute__((noinline,used)) lds_raise_invalid(void) { (void)gmath_invalid(); }
static void __attribute__((noinline,used)) lds_raise_overflow(void) { (void)gmath_overflow(0); }
static void __attribute__((noinline,used)) lds_raise_underflow(void) { (void)gmath_underflow(0); }
static int lds_equal(const ld_value *a,const ld_value *b) {
  return a->kind==b->kind && (ld_top(a)<0 && ld_top(b)<0 && a->kind==LD_FINITE ? 1 : ld_cmp(a,b)==0);
}
static ld_value lds_difference(ld_value a,ld_value b) {
  b.sign^=1;ld_add(&a,&b);a.sign=0;return a;
}
static uint64_t lds_step64(uint64_t u,int direction) {
  uint64_t mag=u&UINT64_C(0x7fffffffffffffff);
  if (!mag) return (direction<0 ? UINT64_C(0x8000000000000000):0)|1;
  if (mag==UINT64_C(0x7ff0000000000000) && ((u>>63) ? direction<0 : direction>0)) return u;
  return ((u>>63) ? direction<0 : direction>0) ? u+1 : u-1;
}
static ld_raw lds_limit(unsigned fmt,int sign) {
  ld_raw r;
  if (fmt==106) {r.hi=UINT64_C(0x7fefffffffffffff);r.lo=UINT64_C(0x7c8fffffffffffff);if(sign)r.lo|=UINT64_C(1)<<63;}
  else if (fmt==64) {r.hi=UINT64_C(0x7fefffffffffffff);r.lo=0;}
  else if (fmt==80) {r.hi=32766;r.lo=UINT64_MAX;}
  else {r.hi=UINT64_C(0x7ffeffffffffffff);r.lo=UINT64_MAX;}
  r.hi|=(uint64_t)sign<<(fmt==80?15:63);return r;
}
/* Every finite sum of two binary64 numbers admits a normalized encoding with
 * nearest binary64 leader (clamped at DBL_MAX) and exact binary64 residual.
 * In the cell containing x and its two boundary cells the leaders are among
 * RN64(x) +/- 2. For a fixed leader, residual rounding and its two neighbors
 * bracket x; all other residuals are farther. Taking the union supplies both
 * DD brackets and nearest rounding, including at a leader midpoint. A cell
 * boundary is itself representable, so a neighbor cannot skip a whole cell.
 * Fifteen candidates is a fixed bound; no convergence assumption is used. */
static ld_raw lds_dd(const ld_value *x,int direction) {
  uint64_t center=ld_pack_single(64,x).hi;
  if ((center&UINT64_C(0x7fffffffffffffff))==UINT64_C(0x7ff0000000000000))
    center=((uint64_t)x->sign<<63)|UINT64_C(0x7fefffffffffffff);
  ld_value limit=ld_decode(106,lds_limit(106,0));
  ld_value best={{0},0,LD_INF,0}, distance={{0},0,LD_INF,0};
  int found=0;
  for(int offset=-2;offset<=2;++offset) {
    uint64_t leader=center;
    for(int i=0;i<(offset<0?-offset:offset);++i)leader=lds_step64(leader,offset<0?-1:1);
    if ((leader&UINT64_C(0x7fffffffffffffff))>=UINT64_C(0x7ff0000000000000))continue;
    ld_value h=ld_decode64(leader),residual=*x;h.sign^=1;ld_add(&residual,&h);
    uint64_t nearest=ld_pack_single(64,&residual).hi;
    for(int step=-1;step<=1;++step) {
      uint64_t low=step ? lds_step64(nearest,step):nearest;
      ld_value candidate=ld_decode64(leader), tail=ld_decode64(low);
      if(tail.kind!=LD_FINITE)continue;
      ld_add(&candidate,&tail);
      if(ld_cmpmag(&candidate,&limit)>0)continue;
      int cmp=lds_equal(&candidate,x)?0:ld_cmp(&candidate,x);
      if(direction && (direction>0 ? cmp<=0:cmp>=0))continue;
      ld_value delta=lds_difference(candidate,*x);
      int c=found?ld_cmpmag(&delta,&distance):-1;
      if(c==0) {
        ld_value gap=lds_difference(candidate,best);
        /* A tie lies halfway across a power-of-two gap: choose even at
         * that gap's unit, rather than assuming a fixed 106-bit lattice. */
        c=ld_bit(&candidate,ld_top(&gap)) ? 1:-1;
      }
      if(c<0) {best=candidate;distance=delta;found=1;}
    }
  }
  if(!found) {best=*x;best.kind=LD_INF;return ld_pack(106,&best);}
  if(!direction && ld_cmpmag(x,&limit)>0) {
    /* The finite population terminates with spacing 2^917. The virtual
     * next value is used only to classify the nearest overflow midpoint. */
    ld_value threshold=limit,half={{0},0,LD_FINITE,0};
    ld_insert(&half,1,916);ld_add(&threshold,&half);
    if(ld_cmpmag(x,&threshold)>=0) {best=*x;best.kind=LD_INF;}
  }
  if(ld_top(&best)<0)best.sign=x->sign;
  return ld_pack(106,&best);
}
static ld_raw lds_single_neighbor(unsigned fmt,const ld_value *a,int direction) {
  if(a->kind==LD_INF)return lds_limit(fmt,a->sign);
  ld_value v=*a;
  int top=ld_top(&v),p=fmt==64?53:fmt==80?64:113;
  int minimum=(fmt==64?-1074:fmt==80?-16445:-16494)-LD_BASE;
  if(top<0) {v.sign=direction<0;ld_set(&v,minimum);return ld_pack(fmt,&v);}
  int outward=v.sign?direction<0:direction>0;
  int cut=top-p+1;
  if(cut<minimum)cut=minimum;
  if(!outward && top>minimum && !ld_any_below(&v,top)) {
    cut=top-p;if(cut<minimum)cut=minimum;
  }
  ld_value unit={{0},!outward,LD_FINITE,0};ld_set(&unit,cut);
  int sign=v.sign;v.sign=0;ld_add(&v,&unit);v.sign=sign;
  return ld_pack(fmt,&v);
}
static void lds_flags(unsigned fmt,ld_raw r,int overflow,int inexact,int adjacent) {
  ld_value v=ld_decode(fmt,r);
  if(overflow) {lds_raise_overflow();return;}
  int minimum=fmt==106?-969:fmt==64?-1022:-16382;
  if((inexact || adjacent) && ld_top(&v)+LD_BASE<minimum) lds_raise_underflow();
  else if(inexact) lds_raise_inexact();
}
/* op0/1/2 = ldexp/scalbn/scalbln; op3/4 = nextafter/nexttoward. */
static ld_raw lds_run(unsigned fmt,int op,ld_raw x,ld_raw y,long exponent) {
  ld_value a=ld_decode(fmt,x),b;
  if(op>=3) {
    b=ld_decode(fmt,y);
    if(a.invalid || b.invalid)lds_raise_invalid();
    if(a.kind==LD_NAN || b.kind==LD_NAN) {a.kind=LD_NAN;return ld_pack(fmt,&a);}
    if(lds_equal(&a,&b))return ld_pack(fmt,&b);
    int direction=ld_cmp(&a,&b)<0?1:-1;
    /* Signed zero is ordered by the destination's nonzero sign. */
    if(ld_top(&a)<0 && a.kind==LD_FINITE)direction=b.sign?-1:1;
    ld_raw r;
    if(fmt==106 && a.kind!=LD_INF)r=lds_dd(&a,direction);
    else r=lds_single_neighbor(fmt,&a,direction);
    ld_value result=ld_decode(fmt,r);
    lds_flags(fmt,r,a.kind==LD_FINITE && result.kind==LD_INF,0,1);return r;
  }
  if(a.invalid)lds_raise_invalid();
  int top=ld_top(&a);
  if(a.kind!=LD_FINITE || top<0)return ld_pack(fmt,&a);
  /* Compare long extrema before narrowing, negation, shifts or addition. */
  int n=exponent>40000L?40000:exponent< -40000L?-40000:(int)exponent;
  int p=fmt==64?53:fmt==80?64:113;
  int minbit=(fmt==106||fmt==64?-1074:fmt==80?-16445:-16494)-LD_BASE;
  int maxexp=fmt==106||fmt==64?1023:16383;
  if(top+LD_BASE+n>maxexp+1) {a.kind=LD_INF;ld_raw r=ld_pack(fmt,&a);lds_flags(fmt,r,1,1,0);return r;}
  if(top+n<minbit-1) {memset(a.w,0,sizeof a.w);ld_raw r=ld_pack(fmt,&a);lds_flags(fmt,r,0,1,0);return r;}
  int inexact=0;
  if(fmt!=106) {
    int cut=top-p+1;if(cut<minbit-n)cut=minbit-n;
    if(cut>0) {
      inexact=ld_any_below(&a,cut);
      int increment=ld_bit(&a,cut-1)&&(ld_any_below(&a,cut-1)||ld_bit(&a,cut));
      ld_clear_below(&a,cut);if(increment)ld_increment(&a,cut);
    }
    ld_shift(&a,n);
  } else {
    int sticky=n<0?ld_any_below(&a,-n):0;
    ld_shift(&a,n);if(sticky)ld_set(&a,0);
  }
  ld_raw r=fmt==106?lds_dd(&a,0):ld_pack(fmt,&a);
  ld_value rounded=ld_decode(fmt,r);
  if(fmt==106)inexact=!lds_equal(&rounded,&a);
  lds_flags(fmt,r,rounded.kind==LD_INF,inexact,0);return r;
}
#endif
