/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Outward fixed-point intervals. No floating-point numerical operation.
 */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_INTERVAL_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_INTERVAL_H
#include <ghoti.io/math/macros.h>
#define LDE_PREC 4352
#define LDE_FW (LDE_PREC/32+2)
typedef struct {uint32_t w[LDE_FW];int sign;} lde_fixed;
typedef struct {lde_fixed lo,hi;} lde_interval;
static int lde_ftop(const lde_fixed *a) {
  for(int i=LDE_FW-1;i>=0;--i)if(a->w[i]) {int k=31;while(!(a->w[i]>>k))--k;return 32*i+k;}
  return -1;
}
static int lde_fcmpmag(const lde_fixed *a,const lde_fixed *b) {
  for(int i=LDE_FW-1;i>=0;--i)if(a->w[i]!=b->w[i])return a->w[i]>b->w[i]?1:-1;
  return 0;
}
static int lde_fcmp(const lde_fixed *a,const lde_fixed *b) {
  if(lde_ftop(a)<0 && lde_ftop(b)<0)return 0;
  if(a->sign!=b->sign)return a->sign?-1:1;
  int c=lde_fcmpmag(a,b);return a->sign?-c:c;
}
static lde_fixed lde_fint(int n) {
  lde_fixed a={{0},n<0};a.w[LDE_PREC/32]=(unsigned)(n<0?-n:n);return a;
}
static void lde_funit(lde_fixed *a) {
  for(int i=0;i<LDE_FW;++i)if(++a->w[i])break;
}
static lde_fixed lde_fadd(lde_fixed a,lde_fixed b) {
  int c=lde_fcmpmag(&a,&b),sub=a.sign!=b.sign;uint64_t carry=0;
  for(int i=0;i<LDE_FW;++i) {
    uint64_t x=sub && c<0?b.w[i]:a.w[i],y=sub && c<0?a.w[i]:b.w[i];
    if(sub) {uint64_t t=y+carry;a.w[i]=(uint32_t)(x-t);carry=x<t;}
    else {uint64_t t=x+y+carry;a.w[i]=(uint32_t)t;carry=t>>32;}
  }
  if(sub && c<0)a.sign=b.sign;
  if(lde_ftop(&a)<0)a.sign=0;
  return a;
}
static lde_fixed lde_fneg(lde_fixed a) {if(lde_ftop(&a)>=0)a.sign^=1;return a;}
static lde_fixed lde_fmul(lde_fixed a,lde_fixed b,int upward) {
  uint32_t product[2*LDE_FW]={0};int at=lde_ftop(&a)/32,bt=lde_ftop(&b)/32;
  for(int i=0;i<=at;++i)if(a.w[i]) {
    uint64_t carry=0;
    for(int j=0;j<=bt;++j) {uint64_t t=(uint64_t)a.w[i]*b.w[j]+product[i+j]+carry;product[i+j]=(uint32_t)t;carry=t>>32;}
    product[i+bt+1]=(uint32_t)carry;
  }
  lde_fixed out={{0},a.sign^b.sign};int lost=0;
  for(int i=0;i<LDE_PREC/32;++i)lost|=product[i]!=0;
  for(int i=0;i<LDE_FW;++i)out.w[i]=product[i+LDE_PREC/32];
  if(lost && upward!=out.sign)lde_funit(&out);
  if(lde_ftop(&out)<0)out.sign=0;
  return out;
}
static lde_fixed lde_fsmall(lde_fixed a,unsigned n,int upward) {
  uint64_t remainder=0;
  for(int i=LDE_FW-1;i>=0;--i) {uint64_t v=(remainder<<32)|a.w[i];a.w[i]=(uint32_t)(v/n);remainder=v%n;}
  if(remainder && upward!=a.sign)lde_funit(&a);
  if(lde_ftop(&a)<0)a.sign=0;
  return a;
}
/* Positive denominator; restoring division retains a nonnegative remainder.
 * Quotient range is bounded by the callers (at most2^15). */
static lde_fixed lde_fdiv(lde_fixed a,lde_fixed b,int upward) {
  lde_fixed rem={{0},0},out={{0},a.sign^b.sign};
  for(int bit=lde_ftop(&a)+LDE_PREC;bit>=0;--bit) {
    for(int i=LDE_FW-1;i>=0;--i)rem.w[i]=(rem.w[i]<<1)|(i?rem.w[i-1]>>31:0);
    int source=bit-LDE_PREC;
    if(source>=0)rem.w[0]|=(a.w[source/32]>>(source%32))&1;
    if(lde_fcmpmag(&rem,&b)>=0) {
      uint64_t borrow=0;
      for(int i=0;i<LDE_FW;++i) {uint64_t sub=(uint64_t)b.w[i]+borrow,x=rem.w[i];rem.w[i]=(uint32_t)(x-sub);borrow=x<sub;}
      if(bit<LDE_FW*32)out.w[bit/32]|=UINT32_C(1)<<(bit%32);
    }
  }
  if(lde_ftop(&rem)>=0 && upward!=out.sign)lde_funit(&out);
  if(lde_ftop(&out)<0)out.sign=0;
  return out;
}
static lde_interval lde_iconvert(const ld_value *a,int shift) {
  lde_fixed out={{0},a->sign};int lost=0;
  for(int bit=0;bit<LD_WORDS*32;++bit)if(ld_bit(a,bit)) {
    int j=bit+LD_BASE+shift+LDE_PREC;
    if(j<0)lost=1;else if(j<LDE_FW*32)out.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  lde_interval v={out,out};
  if(lost) {if(a->sign)lde_funit(&v.lo);else lde_funit(&v.hi);}
  return v;
}
static lde_interval lde_iadd(lde_interval a,lde_interval b) {
  lde_interval out={lde_fadd(a.lo,b.lo),lde_fadd(a.hi,b.hi)};return out;
}
static lde_interval lde_ineg(lde_interval a) {
  lde_interval out={lde_fneg(a.hi),lde_fneg(a.lo)};return out;
}
static lde_interval lde_imul(lde_interval a,lde_interval b) {
  lde_fixed al[4]={lde_fmul(a.lo,b.lo,0),lde_fmul(a.lo,b.hi,0),lde_fmul(a.hi,b.lo,0),lde_fmul(a.hi,b.hi,0)};
  lde_fixed ah[4]={lde_fmul(a.lo,b.lo,1),lde_fmul(a.lo,b.hi,1),lde_fmul(a.hi,b.lo,1),lde_fmul(a.hi,b.hi,1)};
  lde_interval out={al[0],ah[0]};
  for(int i=1;i<4;++i) {if(lde_fcmp(&al[i],&out.lo)<0)out.lo=al[i];if(lde_fcmp(&ah[i],&out.hi)>0)out.hi=ah[i];}
  return out;
}
static lde_interval lde_idiv(lde_interval a,lde_interval b) {
  /* All denominator intervals are strictly positive. */
  lde_interval out;
  out.lo=lde_fdiv(a.lo,a.lo.sign?b.lo:b.hi,0);
  out.hi=lde_fdiv(a.hi,a.hi.sign?b.hi:b.lo,1);return out;
}
static lde_interval lde_iscale(lde_interval a,int n) {
  lde_fixed k=lde_fint(n);lde_interval b={k,k};return lde_imul(a,b);
}
/* atanh(t) for0<=t<=1/3. At iteration j the omitted positive tail is
 * <=(9/8)*t^(2j+3)/(2j+3). After1400 terms it is below2^-4430.
 * Adding one fixed-point unit to the upper sum encloses that tail.
 * Directed products/divisions separately enclose all arithmetic errors. */
static lde_interval lde_atanh(lde_interval t) {
  lde_interval square=lde_imul(t,t),term=t,sum=t;
  for(unsigned j=1;j<1400;++j) {
    term=lde_imul(term,square);
    lde_interval add={lde_fsmall(term.lo,2*j+1,0),lde_fsmall(term.hi,2*j+1,1)};
    sum=lde_iadd(sum,add);
  }
  lde_funit(&sum.hi);return sum;
}
static lde_interval lde_ln2(void) {
  lde_fixed one=lde_fint(1),three=lde_fint(3);lde_interval t={lde_fdiv(one,three,0),lde_fdiv(one,three,1)};
  return lde_iscale(lde_atanh(t),2);
}
static lde_interval lde_log(const ld_value *a,lde_interval ln2) {
  int exponent=ld_top(a)+LD_BASE;
  lde_interval m=lde_iconvert(a,-exponent);lde_fixed one=lde_fint(1);
  lde_interval plus={lde_fadd(m.lo,one),lde_fadd(m.hi,one)};
  one.sign=1;lde_interval minus={lde_fadd(m.lo,one),lde_fadd(m.hi,one)};
  lde_interval t=lde_idiv(minus,plus);
  return lde_iadd(lde_iscale(lde_atanh(t),2),lde_iscale(ln2,exponent));
}
static lde_fixed lde_fshift(lde_fixed a,int shift,int upward) {
  lde_fixed out={{0},a.sign};int lost=0;
  for(int i=0;i<LDE_FW*32;++i)if((a.w[i/32]>>(i%32))&1) {
    int j=i+shift;if(j<0)lost=1;else if(j<LDE_FW*32)out.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  if(lost && upward!=a.sign)lde_funit(&out);
  if(lde_ftop(&out)<0)out.sign=0;
  return out;
}
static ldn_wide lde_fwide(const lde_fixed *a,int exponent,int upper) {
  ldn_wide out={{0},a->sign};int lost=0;
  for(int i=0;i<LDE_FW*32;++i)if((a->w[i/32]>>(i%32))&1) {
    int j=i-LDE_PREC+exponent-LDN_BASE;
    if(j<0)lost=1;else if(j<LDN_WORDS*32)out.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  if(lost && upper!=out.sign) {
    for(int i=0;i<LDN_WORDS;++i)if(++out.w[i])break;
  }
  return out;
}
/* exp(x), x>=0, after subtracting k*ln2, has0<=r<ln2+2^-4200.
 * With r<1, the1000-term Taylor remainder is <3/1001!<2^-8500.
 * One upper unit covers the omitted tail. */
static lde_interval lde_exp_reduced(lde_fixed x,lde_interval ln2,int *exponent) {
  unsigned lo=0,hi=24000;
  while(lo+1<hi) {
    unsigned mid=(lo+hi)/2;lde_fixed k=lde_fint((int)mid),test=lde_fmul(k,ln2.hi,1);
    if(lde_fcmp(&test,&x)<=0)lo=mid;else hi=mid;
  }
  *exponent=(int)lo;
  lde_interval point={x,x},r=lde_iadd(point,lde_ineg(lde_iscale(ln2,(int)lo)));
  lde_fixed one=lde_fint(1);lde_interval sum={one,one},term=sum;
  for(unsigned n=1;n<=1000;++n) {
    term=lde_imul(term,r);term.lo=lde_fsmall(term.lo,n,0);term.hi=lde_fsmall(term.hi,n,1);sum=lde_iadd(sum,term);
  }
  lde_funit(&sum.hi);return sum;
}
static ldn_wide lde_exp_endpoint(lde_fixed x,lde_interval ln2,int upper) {
  int negative=x.sign,exponent; x.sign=0;
  lde_interval result=lde_exp_reduced(x,ln2,&exponent);
  if(negative) {
    lde_fixed one=lde_fint(1);lde_interval reciprocal={lde_fdiv(one,result.hi,0),lde_fdiv(one,result.lo,1)};
    result=reciprocal;exponent=-exponent;
  }
  return lde_fwide(upper?&result.hi:&result.lo,exponent,upper);
}
static int lde_wcmp(const ldn_wide *a,const ldn_wide *b) {
  if(ldn_wtop(a)<0 && ldn_wtop(b)<0)return 0;
  if(a->sign!=b->sign)return a->sign?-1:1;
  int c=0;for(int i=LDN_WORDS-1;i>=0;--i)if(a->w[i]!=b->w[i]) {c=a->w[i]>b->w[i]?1:-1;break;}
  return a->sign?-c:c;
}
/* The selected interval is checked against actual population neighbors.
 * DD uses the union of binary64 residual cells, without a106-bit grid. */
static ld_raw lde_enclosed(unsigned fmt,const ldn_wide *lo,const ldn_wide *hi,int inexact) {
  int maxexp=fmt==64 || fmt==106?1023:16383;
  int minimum=fmt==64 || fmt==106?-1074:fmt==80?-16445:-16494;
  ld_value selected={{0},lo->sign,LD_FINITE,0};
  if(ldn_wtop(lo)+LDN_BASE>maxexp+1) {
    selected.kind=LD_INF;ld_raw out=ld_pack(fmt,&selected);lds_flags(fmt,out,1,1,0);return out;
  }
  if(ldn_wtop(hi)+LDN_BASE<minimum-2) {
    ld_raw out=ld_pack(fmt,&selected);lds_flags(fmt,out,0,1,0);return out;
  }
  selected=ldn_project(lo,1);
  ld_raw out=fmt==106?lds_dd(&selected,0):ld_pack(fmt,&selected);
  ld_value value=ld_decode(fmt,out);
  /* A width bound of2^-3200 relative to the reduced argument is far below
   * the smallest possible DD population gap2^-1074. Neighbor checks also
   * guard the implementation against accidental loss of that precision. */
  if(value.kind!=LD_INF) {
    ld_value prev=ld_decode(fmt,lde_neighbor(fmt,&value,-1)),next=ld_decode(fmt,lde_neighbor(fmt,&value,1));
    ldn_wide before=ldn_widen(&prev),after=ldn_widen(&next);
    if(prev.kind!=LD_INF && lde_wcmp(lo,&before)<0)out=lde_neighbor(fmt,&value,-1);
    else if(next.kind!=LD_INF && lde_wcmp(hi,&after)>0)out=lde_neighbor(fmt,&value,1);
  }
  value=ld_decode(fmt,out);
  if(value.kind==LD_INF) {
    ld_value limit=ld_decode(fmt,lds_limit(fmt,value.sign));ldn_wide boundary=ldn_widen(&limit);
    if(value.sign?lde_wcmp(hi,&boundary)>0:lde_wcmp(lo,&boundary)<0)__builtin_trap();
  } else {
    ld_value prev=ld_decode(fmt,lde_neighbor(fmt,&value,-1)),next=ld_decode(fmt,lde_neighbor(fmt,&value,1));
    ldn_wide before=ldn_widen(&prev),after=ldn_widen(&next);
    if((prev.kind!=LD_INF && lde_wcmp(lo,&before)<0) ||
       (next.kind!=LD_INF && lde_wcmp(hi,&after)>0))__builtin_trap();
  }
  lds_flags(fmt,out,value.kind==LD_INF,inexact,0);return out;
}
#endif
