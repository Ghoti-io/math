/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact dyadic identities and exponent parity. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_EXACT_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_EXACT_H
#include <ghoti.io/math/macros.h>
static int lde_low(const ld_value *a) {
  for(int i=0;i<LD_WORDS*32;++i)if(ld_bit(a,i))return i;
  return -1;
}
static int lde_one(const ld_value *a) {
  return a->kind==LD_FINITE && !a->sign && ld_top(a)==LD_ZERO_BIT && !ld_any_below(a,LD_ZERO_BIT);
}
static int lde_integer(const ld_value *a) {
  return a->kind==LD_FINITE && !ld_any_below(a,LD_ZERO_BIT);
}
static int lde_odd(const ld_value *a) {return lde_integer(a) && ld_bit(a,LD_ZERO_BIT);}
static ld_raw lde_unit(unsigned fmt,int sign) {
  ld_value one={{0},sign,LD_FINITE,0};ld_set(&one,LD_ZERO_BIT);return ld_pack(fmt,&one);
}
static ld_raw lde_domain(unsigned fmt) {
  ld_value a={{0},0,LD_NAN,0};lds_raise_invalid();return ld_pack(fmt,&a);
}
static ld_raw __attribute__((noinline,used)) lde_pole(unsigned fmt,int sign) {
  ld_value a={{0},sign,LD_INF,0};(void)gmath_div_by_zero((uint64_t)sign<<63);return ld_pack(fmt,&a);
}
static ld_raw lde_range(unsigned fmt,int sign,int overflow) {
  ld_value a={{0},sign,overflow?LD_INF:LD_FINITE,0};ld_raw r=ld_pack(fmt,&a);lds_flags(fmt,r,overflow,1,0);return r;
}
static int lde_stop(const lde_small *a) {
  for(int i=LDE_SMALL_WORDS-1;i>=0;--i)if(a->w[i]) {int b=31;while(!(a->w[i]>>b))--b;return i*32+b;}
  return -1;
}
static int lde_ssqrt(lde_small *a) {
  lde_small root={{0}},remainder={{0}};
  for(int p=lde_stop(a)/2;p>=0;--p) {
    lde_sshift(&remainder,2);
    for(int j=0;j<2;++j)remainder.w[0]|=((a->w[(2*p+j)/32]>>((2*p+j)%32))&1)<<j;
    lde_small trial={{0}};trial.w[0]=1;lde_sadd(&trial,&root,4);
    int take=lde_scmp(&remainder,&trial)>=0;if(take)lde_ssub(&remainder,&trial);
    lde_sshift(&root,1);root.w[0]|=(unsigned)take;
  }
  if(lde_stop(&remainder)>=0)return 0;
  *a=root;return 1;
}
static int lde_spower(lde_small *a,unsigned n,int maxbits) {
  lde_small base=*a,out={{0}};out.w[0]=1;
  while(n) {
    if(n&1) {
      lde_small next={{0}};int at=lde_stop(&out)/32,bt=lde_stop(&base)/32;
      if(lde_stop(&out)+lde_stop(&base)>=maxbits)return 0;
      for(int i=0;i<=at;++i)if(out.w[i]) {
        uint64_t carry=0;
        for(int j=0;j<=bt;++j) {uint64_t t=(uint64_t)out.w[i]*base.w[j]+next.w[i+j]+carry;next.w[i+j]=(uint32_t)t;carry=t>>32;}
        next.w[i+bt+1]=(uint32_t)carry;
      }
      out=next;if(lde_stop(&out)>=maxbits)return 0;
    }
    n>>=1;if(!n)break;
    lde_small next={{0}};int bt=lde_stop(&base)/32;
    if(2*lde_stop(&base)>=maxbits)return 0;
    for(int i=0;i<=bt;++i)if(base.w[i]) {
      uint64_t carry=0;
      for(int j=0;j<=bt;++j) {uint64_t t=(uint64_t)base.w[i]*base.w[j]+next.w[i+j]+carry;next.w[i+j]=(uint32_t)t;carry=t>>32;}
      next.w[i+bt+1]=(uint32_t)carry;
    }
    base=next;
  }
  *a=out;return 1;
}
/* Return1 only when the algebra determines an exact dyadic result (possibly
 * outside the finite range);0 delegates a nonexact power to intervals. */
static int lde_exact_pow(unsigned fmt,const ld_value *a,const ld_value *b,int sign,ld_raw *out) {
  int low=lde_low(a),xe=low+LD_BASE,ylow=lde_low(b),ye=ylow+LD_BASE;
  int k=ye<0?-ye:0,at=ld_top(a)-low;
  if(k>15 && xe)return 0;
  if(k<=15 && xe%((int)1<<k))return 0;
  lde_small odd={{0}};
  for(int i=0;i<=at;++i)if(ld_bit(a,low+i))odd.w[i/32]|=UINT32_C(1)<<(i%32);
  if(at && k>11)return 0;
  if(at)for(int j=0;j<k;++j)if(!lde_ssqrt(&odd))return 0;
  if(k<=15)xe/=((int)1<<k);else xe=0;
  int yt=ld_top(b)-ylow;
  if(!at) {
    /* The exponent product is streamed with saturation before any cast. */
    int magnitude=0;
    for(int i=ld_top(b);i>=LD_ZERO_BIT-k;--i) {
      if(magnitude>40000)break;
      magnitude=magnitude*2+ld_bit(b,i);
    }
    if(magnitude>40000 || (xe && magnitude>40000/(xe<0?-xe:xe)))magnitude=40001;
    else magnitude*=xe<0?-xe:xe;
    int negative=(xe<0)^b->sign,e=negative?-magnitude:magnitude;
    int min=fmt==64 || fmt==106?-1074:fmt==80?-16445:-16494,max=fmt==64 || fmt==106?1023:16383;
    if(e>max) {*out=lde_range(fmt,sign,1);return 1;}
    if(e<min) {*out=lde_range(fmt,sign,0);return 1;}
    ld_value exact={{0},sign,LD_FINITE,0};ld_insert(&exact,1,e);*out=ld_pack(fmt,&exact);return 1;
  }
  if(b->sign || yt>11 || ye>11)return 0;
  unsigned n=0;
  for(int i=ld_top(b);i>=LD_ZERO_BIT-k;--i)n=(n<<1)|(unsigned)ld_bit(b,i);
  if(!lde_spower(&odd,n,fmt==106?2098:fmt==64?53:fmt==80?64:113))return 0;
  int exponent=xe*(int)n,top=lde_stop(&odd);
  if(exponent<LD_BASE || exponent+top>=LD_BASE+LD_WORDS*32)return 0;
  ld_value exact={{0},sign,LD_FINITE,0};
  for(int i=0;i<=top;++i)if((odd.w[i/32]>>(i%32))&1)ld_set(&exact,i+exponent-LD_BASE);
  ld_raw raw=fmt==106?lds_dd(&exact,0):ld_pack(fmt,&exact);ld_value decoded=ld_decode(fmt,raw);
  if(!lds_equal(&decoded,&exact))return 0;
  *out=raw;return 1;
}
static int lde_ten_power(unsigned fmt,const ld_value *a,int *power) {
  int bound=fmt==106?904:fmt==64?22:fmt==80?27:48;
  lde_small odd={{0}};odd.w[0]=1;
  for(int n=0;n<=bound;++n) {
    int top=lde_stop(&odd),target=ld_top(a)+LD_BASE;
    if(top+n==target) {
      ld_value candidate={{0},0,LD_FINITE,0};
      for(int j=0;j<=top;++j)if((odd.w[j/32]>>(j%32))&1)ld_set(&candidate,j+n-LD_BASE);
      if(lds_equal(&candidate,a)) {*power=n;return 1;}
    }
    if(top+n>target)break;
    lde_small copy=odd;lde_sadd(&odd,&copy,4);
  }
  return 0;
}
#endif
