/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Normalized outward dyadic intervals. The exponent is independent of the
 * significand, including when a result exceeds the native exponent range.
 * Numerical operations are exclusively unsigned integer operations.
 */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_SEVENTEEN_INTERVAL_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_SEVENTEEN_INTERVAL_H
#include <ghoti.io/math/macros.h>

typedef struct { lde_interval m; int e; } lds17_interval;
static lds17_interval lds17_normal(lde_interval m,int e) {
  int a=lde_ftop(&m.lo),b=lde_ftop(&m.hi),top=a>b?a:b;
  if(top<0) {lds17_interval z={m,0};return z;}
  int shift=LDE_PREC-top;
  m.lo=lde_fshift(m.lo,shift,0);m.hi=lde_fshift(m.hi,shift,1);
  lds17_interval out={m,e-shift};return out;
}
static lds17_interval lds17_int(int n) {
  lde_fixed f=lde_fint(n);lde_interval m={f,f};return lds17_normal(m,0);
}
static lds17_interval lds17_from(const ld_value *a) {
  int e=ld_top(a)+LD_BASE;
  if(ld_top(a)<0)return lds17_int(0);
  return lds17_normal(lde_iconvert(a,-e),e);
}
static lds17_interval lds17_neg(lds17_interval a) {a.m=lde_ineg(a.m);return a;}
static lds17_interval lds17_shift(lds17_interval a,int n) {a.e+=n;return a;}
static lds17_interval lds17_add(lds17_interval a,lds17_interval b) {
  if(lde_ftop(&a.m.lo)<0 && lde_ftop(&a.m.hi)<0)return b;
  if(lde_ftop(&b.m.lo)<0 && lde_ftop(&b.m.hi)<0)return a;
  int e=a.e>b.e?a.e:b.e;
  a.m.lo=lde_fshift(a.m.lo,a.e-e,0);a.m.hi=lde_fshift(a.m.hi,a.e-e,1);
  b.m.lo=lde_fshift(b.m.lo,b.e-e,0);b.m.hi=lde_fshift(b.m.hi,b.e-e,1);
  return lds17_normal(lde_iadd(a.m,b.m),e);
}
static lds17_interval lds17_sub(lds17_interval a,lds17_interval b) {return lds17_add(a,lds17_neg(b));}
static lds17_interval lds17_mul(lds17_interval a,lds17_interval b) {
  return lds17_normal(lde_imul(a.m,b.m),a.e+b.e);
}
static lds17_interval lds17_div(lds17_interval a,lds17_interval b) {
  lde_fixed zero=lde_fint(0);
  if(lde_fcmp(&b.m.lo,&zero)<=0 && lde_fcmp(&b.m.hi,&zero)>=0)__builtin_trap();
  if(b.m.hi.sign) {a=lds17_neg(a);b=lds17_neg(b);}
  return lds17_normal(lde_idiv(a.m,b.m),a.e-b.e);
}
/* Exact small-integer product before directed normalization. Normalized
 * mantissas have4352 fractional bits and64 spare integer bits. */
static lds17_interval lds17_times_unsigned(lds17_interval a,unsigned n) {
  lde_fixed *endpoints[2]={&a.m.lo,&a.m.hi};
  for(unsigned k=0;k<2;++k) {
    uint64_t carry=0;
    for(int j=0;j<LDE_FW;++j) {uint64_t v=(uint64_t)endpoints[k]->w[j]*n+carry;endpoints[k]->w[j]=(uint32_t)v;carry=v>>32;}
    if(carry)__builtin_trap();
  }
  return lds17_normal(a.m,a.e);
}
static lds17_interval lds17_small(lds17_interval a,unsigned n) {
  a.m.lo=lde_fsmall(a.m.lo,n,0);a.m.hi=lde_fsmall(a.m.hi,n,1);
  return lds17_normal(a.m,a.e);
}
static lde_fixed lds17_endpoint(lds17_interval a,int upper) {
  return lde_fshift(upper?a.m.hi:a.m.lo,a.e,upper);
}
static lds17_interval lds17_pi(void) {
  lde_fixed p={{0},0};memcpy(p.w,lds17_pi_floor,sizeof p.w);
  lde_interval m={p,p};lde_funit(&m.hi);return lds17_normal(m,0);
}
static lds17_interval lds17_ln2(void) {
  lde_fixed c={{0},0};memcpy(c.w,lds17_ln2_floor,sizeof c.w);
  lde_interval m={c,c};lde_funit(&m.hi);return lds17_normal(m,0);
}
static lds17_interval lds17_log(lds17_interval a,lds17_interval ln2) {
  /* a.m is in[1,2] and positive. Its logarithm uses the uniformly
   * convergent atanh((m-1)/(m+1)) series with argument <=1/3. */
  lde_fixed one=lde_fint(1);lde_interval unit={one,one};
  lde_interval t=lde_idiv(lde_iadd(a.m,lde_ineg(unit)),lde_iadd(a.m,unit));
  /* A narrow enclosure can straddle a power of two, making t.lo
   * negative. The reused series rounds every operation outward but adds
   * its analytic tail only above. Add the corresponding lower radius;
   * |t|<=1/3+2^-4300 keeps the1400-term tail below one fixed unit. */
  lde_interval series=lde_atanh(t);lde_fixed lower_radius={{0},1};lower_radius.w[0]=1;
  series.lo=lde_fadd(series.lo,lower_radius);
  lds17_interval logm=lds17_normal(lde_iscale(series,2),0);
  return lds17_add(logm,lds17_mul(lds17_int(a.e),ln2));
}
static lds17_interval lds17_exp(lds17_interval a,lds17_interval ln2) {
  lde_interval l2={lds17_endpoint(ln2,0),lds17_endpoint(ln2,1)};
  lde_fixed xlo=lds17_endpoint(a,0),xhi=lds17_endpoint(a,1);
  int elo,ehi;lds17_interval lo,hi;
  if(xlo.sign) {
    xlo.sign=0;lde_interval t=lde_exp_reduced(xlo,l2,&elo);
    lde_fixed one=lde_fint(1);lde_interval r={lde_fdiv(one,t.hi,0),lde_fdiv(one,t.lo,1)};
    lo=lds17_normal(r,-elo);
  } else {lde_interval t=lde_exp_reduced(xlo,l2,&elo);lo=lds17_normal(t,elo);}
  if(xhi.sign) {
    xhi.sign=0;lde_interval t=lde_exp_reduced(xhi,l2,&ehi);
    lde_fixed one=lde_fint(1);lde_interval r={lde_fdiv(one,t.hi,0),lde_fdiv(one,t.lo,1)};
    hi=lds17_normal(r,-ehi);
  } else {lde_interval t=lde_exp_reduced(xhi,l2,&ehi);hi=lds17_normal(t,ehi);}
  int e=lo.e>hi.e?lo.e:hi.e;
  lde_interval m={lde_fshift(lo.m.lo,lo.e-e,0),lde_fshift(hi.m.hi,hi.e-e,1)};
  return lds17_normal(m,e);
}
/* Integer restoring square root of a*2^LDE_PREC. The remainder is exact;
 * floor and floor+one are directed endpoints. This consumes no host sqrt. */
static lde_fixed lds17_sqrt_endpoint(lde_fixed a,int upper) {
  lde_fixed root={{0},0},rem={{0},0};
  int top=lde_ftop(&a)+LDE_PREC;
  for(int p=top/2;p>=0;--p) {
    rem=lde_fshift(rem,2,0);
    for(int j=0;j<2;++j) {
      int source=2*p+j-LDE_PREC;
      if(source>=0 && source<LDE_FW*32)rem.w[0]|=((a.w[source/32]>>(source%32))&1)<<j;
    }
    lde_fixed trial=lde_fshift(root,2,0);trial.w[0]|=1;
    int take=lde_fcmpmag(&rem,&trial)>=0;
    if(take) {trial.sign=1;rem=lde_fadd(rem,trial);}
    root=lde_fshift(root,1,0);root.w[0]|=(unsigned)take;
  }
  if(upper && lde_ftop(&rem)>=0)lde_funit(&root);
  return root;
}
static lds17_interval lds17_sqrt(lds17_interval a) {
  int e=a.e;
  if(e%2) {a.m.lo=lde_fshift(a.m.lo,1,0);a.m.hi=lde_fshift(a.m.hi,1,1);--e;}
  lde_interval m={lds17_sqrt_endpoint(a.m.lo,0),lds17_sqrt_endpoint(a.m.hi,1)};
  return lds17_normal(m,e/2);
}
static lds17_interval lds17_atan(lds17_interval x) {
  int negative=x.m.lo.sign;if(negative)x=lds17_neg(x);
  int reciprocal=x.e>=0;
  lds17_interval one=lds17_int(1);
  if(reciprocal)x=lds17_div(one,x);
  /* Eight half-angle reductions put0<=t<1/256. The512-term alternating
   * series remainder is <=t^1025/1025<2^-8200. A directed interval for
   * the first omitted term is added symmetrically to retain both signs. */
  for(int j=0;j<8;++j)x=lds17_div(x,lds17_add(one,lds17_sqrt(lds17_add(one,lds17_mul(x,x)))));
  lds17_interval square=lds17_neg(lds17_mul(x,x)),term=x,sum=x;
  for(unsigned n=1;n<512;++n) {term=lds17_mul(term,square);sum=lds17_add(sum,lds17_small(term,2*n+1));}
  term=lds17_small(lds17_mul(term,square),1025);
  if(term.m.lo.sign)term=lds17_neg(term);
  lds17_interval radius=term;radius.m.lo=lde_fneg(radius.m.hi);
  sum=lds17_shift(lds17_add(sum,radius),8);
  if(reciprocal)sum=lds17_sub(lds17_shift(lds17_pi(),-1),sum);
  return negative?lds17_neg(sum):sum;
}
/* Full-product reduction. The generator proves |x-k*pi/2|>2^-49396 for
 * k!=0 on the entire supported dyadic grid. The invpi truncation contributes
 * <2^-58624, so the quadrant and residual sign cannot be lost. Only after
 * taking the exact signed fractional residual do we normalize to4352 bits. */
static lds17_interval lds17_reduce(const ld_value *a,unsigned *quadrant) {
  enum { W=LD_WORDS+LDS17_REDUCTION_BITS/32+1 };
  uint32_t product[W]={0};
  for(int i=0;i<LD_WORDS;++i)if(a->w[i]) {
    uint64_t carry=0;
    for(int j=0;j<LDS17_REDUCTION_BITS/32;++j) {
      uint64_t t=(uint64_t)a->w[i]*lds17_two_over_pi[j]+product[i+j]+carry;
      product[i+j]=(uint32_t)t;carry=t>>32;
    }
    product[i+LDS17_REDUCTION_BITS/32]=(uint32_t)carry;
  }
  int cut=LDS17_REDUCTION_BITS-LD_BASE;
  unsigned q=0;for(int j=0;j<2;++j)q|=((product[(cut+j)/32]>>((cut+j)%32))&1)<<j;
  int reflect=(int)((product[(cut-1)/32]>>((cut-1)%32))&1);
  for(int i=(cut+31)/32;i<W;++i)product[i]=0;
  if(cut%32)product[cut/32]&=(UINT32_C(1)<<(cut%32))-1;
  if(reflect) {
    uint64_t carry=1;
    for(int i=0;i<(cut+31)/32;++i) {uint64_t t=(uint64_t)(~product[i])+carry;product[i]=(uint32_t)t;carry=t>>32;}
    if(cut%32)product[cut/32]&=(UINT32_C(1)<<(cut%32))-1;
    q=(q+1)&3;
  }
  int top=cut-1;while(top>=0 && !((product[top/32]>>(top%32))&1))--top;
  /* k=0 needs no irrational separation: the exact original x is the
   * reduced argument and is already available on the full input grid. */
  if(q==0 && ld_top(a)+LD_BASE<0) {*quadrant=0;return lds17_from(a);}
  if(top<0)__builtin_trap();
  lde_fixed m={{0},reflect};int lost=0;
  for(int i=0;i<=top;++i)if((product[i/32]>>(i%32))&1) {
    int j=i-top+LDE_PREC;
    if(j<0)lost=1;else m.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  lde_interval r={m,m};
  if(lost) {if(reflect)lde_funit(&r.lo);else lde_funit(&r.hi);}
  /* The product used floor(2/pi); exact reduced x*2/pi lies above it.
   * Add the certified absolute error as an interval, then multiply pi/2. */
  lds17_interval out=lds17_normal(r,top-cut);
  lds17_interval error=lds17_shift(lds17_int(1),16384-LDS17_REDUCTION_BITS);
  error.m.lo=lde_fint(0);
  out=lds17_mul(lds17_add(out,error),lds17_shift(lds17_pi(),-1));
  if(a->sign) {out=lds17_neg(out);q=(-q)&3;}
  *quadrant=q;return out;
}
static void lds17_sincos(lds17_interval x,lds17_interval *s,lds17_interval *c) {
  lds17_interval square=lds17_neg(lds17_mul(x,x)),st=x,ct=lds17_int(1),ss=st,cs=ct;
  unsigned n;
  for(n=1;;++n) {
    st=lds17_small(lds17_mul(st,square),(2*n)*(2*n+1));
    ct=lds17_small(lds17_mul(ct,square),(2*n-1)*(2*n));
    ss=lds17_add(ss,st);cs=lds17_add(cs,ct);
    if(n>=16 && st.e<x.e-4400 && ct.e< -4400)break;
  }
  /* Alternating-series error is bounded by the next term. Symmetric
   * radii preserve relative accuracy even for a minimum-subnormal x. */
  st=lds17_small(lds17_mul(st,square),(2*n+2)*(2*n+3));
  ct=lds17_small(lds17_mul(ct,square),(2*n+1)*(2*n+2));
  if(st.m.lo.sign)st=lds17_neg(st);
  if(ct.m.lo.sign)ct=lds17_neg(ct);
  st.m.lo=lde_fneg(st.m.hi);ct.m.lo=lde_fneg(ct.m.hi);
  *s=lds17_add(ss,st);*c=lds17_add(cs,ct);
}
static ld_raw lds17_round(unsigned fmt,lds17_interval a) {
  int maximum=fmt==64 || fmt==106?1023:16383;
  int minimum=fmt==64 || fmt==106?-1074:fmt==80?-16445:-16494;
  if(a.e>maximum+2)return lde_range(fmt,a.m.lo.sign,1);
  if(a.e<minimum-4)return lde_range(fmt,a.m.lo.sign,0);
  ldn_wide lo=lde_fwide(&a.m.lo,a.e,0),hi=lde_fwide(&a.m.hi,a.e,1);
  return lde_enclosed(fmt,&lo,&hi,1);
}
#endif
