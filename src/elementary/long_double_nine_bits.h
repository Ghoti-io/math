/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact integer conversion, division, difference and fused product/sum.
 * The product grid extends the unchanged foundation grid in both directions:
 * binary128 minsub squared is 2^-32988, and the largest product is <2^32768.
 * IBM DD operands remain exact sums, never fixed-106-bit approximations. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_NINE_BITS_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_NINE_BITS_H
#include <ghoti.io/math/macros.h>
#define LDN_BASE (2 * LD_BASE)
#define LDN_WORDS (2 * LD_WORDS)
typedef struct { uint32_t w[LDN_WORDS]; int sign; } ldn_wide;
enum { LDN_FMOD, LDN_REMAINDER, LDN_REMQUO, LDN_FDIM, LDN_FMA };
static int ldn_mode(void) {
#if LD_NATIVE == 80 && (defined(__i386__) || defined(__x86_64__))
  uint16_t control;
  __asm__ volatile("fnstcw %0" : "=m"(control) : : "memory");
  return (int)((control >> 10) & 3u);
#else
  return nearby_mode();
#endif
}
static int64_t ldn_integer(unsigned fmt, ld_raw raw, int current,
                           int mode, unsigned bits) {
  ld_value a=ld_decode(fmt,raw);
  uint64_t maximum=bits==32 ? INT32_MAX : INT64_MAX;
  if(a.kind!=LD_FINITE || ld_top(&a)>=LD_ZERO_BIT+64) {
    lds_raise_invalid();return -(int64_t)maximum-1;
  }
  int fractional=ld_any_below(&a,LD_ZERO_BIT);
  uint64_t magnitude=0;
  for(int i=63;i>=0;--i)magnitude=(magnitude<<1)|(unsigned)ld_bit(&a,LD_ZERO_BIT+i);
  int increment=0;
  if(fractional) {
    if(!current) increment=ld_bit(&a,LD_ZERO_BIT-1);
    else if(mode==1) increment=a.sign;
    else if(mode==2) increment=!a.sign;
    else if(mode!=3) increment=ld_bit(&a,LD_ZERO_BIT-1) &&
      (ld_any_below(&a,LD_ZERO_BIT-1)||(magnitude&1));
  }
  /* Check the rounded magnitude without overflowing the unsigned accumulator. */
  uint64_t limit=maximum+(unsigned)a.sign;
  if(magnitude>limit || (increment && magnitude==limit)) {
    lds_raise_invalid();return -(int64_t)maximum-1;
  }
  magnitude+=(unsigned)increment;
  if(current && fractional)lds_raise_inexact();
  if(a.sign && magnitude==maximum+1)return -(int64_t)maximum-1;
  return a.sign ? -(int64_t)magnitude : (int64_t)magnitude;
}
static int ldn_wbit(const ldn_wide *a,int bit) {
  return bit>=0 && bit<32*LDN_WORDS ? (int)((a->w[bit/32]>>(bit%32))&1):0;
}
static int ldn_wtop(const ldn_wide *a) {
  for(int i=LDN_WORDS-1;i>=0;--i)if(a->w[i]) {
    unsigned k=31;while(!(a->w[i]>>k))--k;return 32*i+(int)k;
  }
  return -1;
}
static int ldn_wlost(const ldn_wide *a,int cut) {
  if(cut<=0)return 0;
  if(cut>32*LDN_WORDS)cut=32*LDN_WORDS;
  for(int i=0;i<cut/32;++i)if(a->w[i])return 1;
  return cut%32 && (a->w[cut/32]&((UINT32_C(1)<<(cut%32))-1));
}
static void ldn_wadd(ldn_wide *a,const ldn_wide *b) {
  int cmp=0;
  for(int i=LDN_WORDS-1;i>=0;--i)if(a->w[i]!=b->w[i]) {
    cmp=a->w[i]>b->w[i]?1:-1;break;
  }
  int subtract=a->sign!=b->sign;uint64_t carry=0;
  for(int i=0;i<LDN_WORDS;++i) {
    uint64_t x=subtract && cmp<0?b->w[i]:a->w[i];
    uint64_t y=subtract && cmp<0?a->w[i]:b->w[i];
    if(subtract) {uint64_t t=y+carry;a->w[i]=(uint32_t)(x-t);carry=x<t;}
    else {uint64_t t=x+y+carry;a->w[i]=(uint32_t)t;carry=t>>32;}
  }
  if(subtract && cmp<0)a->sign=b->sign;
}
static ldn_wide ldn_widen(const ld_value *a) {
  ldn_wide out={{0},a->sign};
  const unsigned shift=(unsigned)(LD_BASE-LDN_BASE),k=shift/32,t=shift%32;
  for(unsigned i=0;i<LD_WORDS;++i) {
    out.w[i+k]|=a->w[i]<<t;
    if(t)out.w[i+k+1]|=a->w[i]>>(32-t);
  }
  return out;
}
static ldn_wide ldn_product(const ld_value *a,const ld_value *b) {
  ldn_wide out={{0},a->sign^b->sign};
  int at=ld_top(a)/32,bt=ld_top(b)/32;
  for(int i=0;i<=at;++i)if(a->w[i]) {
    uint64_t carry=0;
    for(int j=0;j<=bt;++j) {
      uint64_t t=(uint64_t)a->w[i]*b->w[j]+out.w[i+j]+carry;
      out.w[i+j]=(uint32_t)t;carry=t>>32;
    }
    out.w[i+bt+1]=(uint32_t)carry;
  }
  return out;
}
/* Project only after the exact sum. A sticky bit below the foundation floor
 * is sufficient for DD (whose minimum component is 2^-1074); single formats
 * first round on their own full product grid, retaining all halfway bits. */
static ld_value ldn_project(const ldn_wide *a,int sticky) {
  ld_value out={{0},a->sign,LD_FINITE,0};
  int shift=LD_BASE-LDN_BASE;
  for(int i=0;i<LD_WORDS*32;++i)if(ldn_wbit(a,i+shift))ld_set(&out,i);
  if(sticky && ldn_wlost(a,shift))ld_set(&out,0);
  return out;
}
static ld_raw ldn_round(unsigned fmt,ldn_wide *a,int mode) {
  int top=ldn_wtop(a),sign=a->sign;
  int maxexp=fmt==64 || fmt==106?1023:16383;
  ld_value result={{0},sign,LD_FINITE,0};
  if(top<0)return ld_pack(fmt,&result);
  /* A sum whose leading exponent exceeds the format by more than one cannot
   * round finite. Avoid projecting any such bits outside the old grid. */
  if(top+LDN_BASE>maxexp+1) {
    lds_raise_overflow();
    if(mode==3 || (mode==1 && !sign) || (mode==2 && sign))return lds_limit(fmt,sign);
    result.kind=LD_INF;return ld_pack(fmt,&result);
  }
  if(fmt==106) {
    result=ldn_project(a,1);
    ld_value limit=ld_decode(fmt,lds_limit(fmt,sign));
    if(mode>0 && ld_cmpmag(&result,&limit)>0) {
      int inward=mode==3 || (mode==1 && !sign) || (mode==2 && sign);
      if(!inward) {
        result.kind=LD_INF;ld_raw raw=ld_pack(fmt,&result);
        lds_flags(fmt,raw,1,1,0);return raw;
      }
      ld_value virtual_next=limit,unit={{0},0,LD_FINITE,0};
      virtual_next.sign=0;ld_insert(&unit,1,917);ld_add(&virtual_next,&unit);
      ld_raw raw=lds_limit(fmt,sign);
      lds_flags(fmt,raw,ld_cmpmag(&result,&virtual_next)>=0,1,0);return raw;
    }
    ld_raw nearest=lds_dd(&result,0);
    ld_value n=ld_decode(fmt,nearest);
    int inexact=!lds_equal(&result,&n);
    ld_raw rounded=nearest;
    if(mode>0 && inexact) {
      int direction=mode==1?-1:mode==2?1:sign?1:-1;
      int cmp=n.kind==LD_INF?(sign?-1:1):ld_cmp(&n,&result);
      if((direction>0 && cmp<0)||(direction<0 && cmp>0))
        rounded=lds_dd(&result,direction);
      /* A strict inward bracket also exists when nearest is infinity. */
      else if(n.kind==LD_INF && ((direction>0)==sign))rounded=lds_limit(fmt,sign);
    }
    ld_value r=ld_decode(fmt,rounded);
    int overflow=r.kind==LD_INF;
    if(!overflow && ld_cmpmag(&result,&limit)>0) {
      ld_value virtual_next=limit,unit={{0},0,LD_FINITE,0};
      virtual_next.sign=0;ld_insert(&unit,1,917);ld_add(&virtual_next,&unit);
      overflow=ld_cmpmag(&result,&virtual_next)>=0;
    }
    lds_flags(fmt,rounded,overflow,inexact,0);return rounded;
  }
  int p=fmt==64?53:fmt==80?64:113;
  int minimum=fmt==64?-1074:fmt==80?-16445:-16494;
  int cut=top-p+1;
  if(cut<minimum-LDN_BASE)cut=minimum-LDN_BASE;
  int lost=ldn_wlost(a,cut),increment=0;
  if(mode==1)increment=lost && sign;
  else if(mode==2)increment=lost && !sign;
  else if(mode!=3)increment=ldn_wbit(a,cut-1) &&
    (ldn_wlost(a,cut-1)||ldn_wbit(a,cut));
  for(int i=0;i<cut/32;++i)a->w[i]=0;
  if(cut%32)a->w[cut/32]&=~((UINT32_C(1)<<(cut%32))-1);
  if(increment) {
    int b=cut;
    while(ldn_wbit(a,b)) {a->w[b/32]&=~(UINT32_C(1)<<(b%32));++b;}
    a->w[b/32]|=UINT32_C(1)<<(b%32);
  }
  if(ldn_wtop(a)+LDN_BASE>maxexp) {
    lds_raise_overflow();
    if(mode==3 || (mode==1 && !sign) || (mode==2 && sign))return lds_limit(fmt,sign);
    result.kind=LD_INF;return ld_pack(fmt,&result);
  }
  result=ldn_project(a,0);ld_raw raw=ld_pack(fmt,&result);
  lds_flags(fmt,raw,0,lost,0);return raw;
}
static ld_raw ldn_remainder(unsigned fmt,int op,ld_value a,ld_value b,int *q) {
  int sign=a.sign,original_sign=a.sign,qsign=a.sign^b.sign;
  a.sign=b.sign=0;unsigned quotient=0;
  int gap=ld_top(&a)-ld_top(&b);
  if(gap>=0) {
    /* Binary formats have at most113 significant bits. Stream the quotient
     * positions through a four-limb residual, retaining all quotient zero
     * bits and only its low seven bits. No fixed precision is used for DD:
     * that format deliberately has no remainder API. */
    uint32_t r[4]={0},d[4]={0};int at=ld_top(&a),bt=ld_top(&b);
    for(int i=0;i<113;++i) {
      r[i/32]|=(uint32_t)ld_bit(&a,at-112+i)<<(i%32);
      d[i/32]|=(uint32_t)ld_bit(&b,bt-112+i)<<(i%32);
    }
    for(int shift=gap;shift>=0;--shift) {
      int cmp=0;
      for(int i=3;i>=0;--i)if(r[i]!=d[i]) {cmp=r[i]>d[i]?1:-1;break;}
      int take=cmp>=0;
      if(take) {
        uint64_t borrow=0;
        for(int i=0;i<4;++i) {uint64_t sub=(uint64_t)d[i]+borrow,old=r[i];r[i]=(uint32_t)(old-sub);borrow=old<sub;}
      }
      quotient=((quotient<<1)|(unsigned)take)&127;
      if(shift)for(int i=3;i>=0;--i)r[i]=(r[i]<<1)|(i?r[i-1]>>31:0);
    }
    memset(a.w,0,sizeof a.w);
    for(int i=0;i<113;++i)if((r[i/32]>>(i%32))&1)ld_set(&a,bt-112+i);
  }
  if(op!=LDN_FMOD) {
    ld_value twice=a;ld_shift(&twice,1);
    int cmp=ld_cmpmag(&twice,&b);
    if(cmp>0 || (!cmp && (quotient&1))) {
      ld_value minus=a;minus.sign=1;a=b;ld_add(&a,&minus);
      quotient=(quotient+1)&127;sign^=1;
    }
  }
  if(ld_top(&a)<0)sign=original_sign;
  a.sign=sign;
  if(q)*q=qsign?-(int)quotient:(int)quotient;
  return ld_pack(fmt,&a);
}
static ld_raw ldn_run(unsigned fmt,int op,ld_raw x,ld_raw y,ld_raw z,int mode,int *q) {
  ld_value a=ld_decode(fmt,x),b=ld_decode(fmt,y),c={{0},0,LD_FINITE,0};
  if(q)*q=0;
  if(op==LDN_FMA)c=ld_decode(fmt,z);
  int invalid=a.invalid||b.invalid||c.invalid;
  if(op==LDN_FMA) {
    int az=a.kind==LD_FINITE && ld_top(&a)<0,bz=b.kind==LD_FINITE && ld_top(&b)<0;
    invalid|=(a.kind==LD_INF && bz)||(b.kind==LD_INF && az);
  }
  if(invalid)lds_raise_invalid();
  if(invalid || a.kind==LD_NAN || b.kind==LD_NAN || c.kind==LD_NAN) {
    a.kind=LD_NAN;return ld_pack(fmt,&a);
  }
  if(op<=LDN_REMQUO) {
    if(a.kind==LD_INF || (b.kind==LD_FINITE && ld_top(&b)<0)) {
      lds_raise_invalid();a.kind=LD_NAN;return ld_pack(fmt,&a);
    }
    if(b.kind==LD_INF || ld_top(&a)<0)return ld_pack(fmt,&a);
    return ldn_remainder(fmt,op,a,b,q);
  }
  if(op==LDN_FDIM) {
    if(lds_equal(&a,&b) || ld_cmp(&a,&b)<=0) {ld_value zero={{0},0,LD_FINITE,0};return ld_pack(fmt,&zero);}
    if(a.kind==LD_INF || b.kind==LD_INF) {a.sign=0;a.kind=LD_INF;return ld_pack(fmt,&a);}
    ldn_wide sum=ldn_widen(&a),minus=ldn_widen(&b);minus.sign^=1;
    ldn_wadd(&sum,&minus);return ldn_round(fmt,&sum,0);
  }
  int ps=a.sign^b.sign;
  if(a.kind==LD_INF || b.kind==LD_INF) {
    if(c.kind==LD_INF && ps!=c.sign) {lds_raise_invalid();a.kind=LD_NAN;return ld_pack(fmt,&a);}
    a.kind=LD_INF;a.sign=ps;return ld_pack(fmt,&a);
  }
  if(c.kind==LD_INF)return ld_pack(fmt,&c);
  ldn_wide product=ldn_product(&a,&b),addend=ldn_widen(&c);
  ldn_wadd(&product,&addend);
  if(ldn_wtop(&product)<0)product.sign=ps==c.sign?ps:mode==1;
  return ldn_round(fmt,&product,mode);
}
#endif
