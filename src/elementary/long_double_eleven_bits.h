/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Integer roots. The restoring recurrences retain a strict floor enclosure;
 * final selection compares exact powers of the unprojected midpoint sum. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_BITS_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_BITS_H
#include <ghoti.io/math/macros.h>
#define LDE_SMALL_WORDS 216
#define LDE_EXACT_WORDS (3*LD_WORDS+4)
typedef struct {uint32_t w[LDE_SMALL_WORDS];} lde_small;
typedef struct {uint32_t w[LDE_EXACT_WORDS];} lde_exact;
enum {LDE_SQRT,LDE_CBRT,LDE_HYPOT,LDE_EXP,LDE_EXP2,LDE_EXPM1,LDE_LOG,LDE_LOG2,LDE_LOG10,LDE_LOG1P,LDE_POW};
static int lde_scmp(const lde_small *a,const lde_small *b) {
  for(int i=LDE_SMALL_WORDS-1;i>=0;--i)if(a->w[i]!=b->w[i])return a->w[i]>b->w[i]?1:-1;
  return 0;
}
static void lde_sshift(lde_small *a,unsigned bits) {
  for(int i=LDE_SMALL_WORDS-1;i>=0;--i)a->w[i]=(a->w[i]<<bits)|(i?a->w[i-1]>>(32-bits):0);
}
static void lde_sadd(lde_small *a,const lde_small *b,unsigned multiplier) {
  uint64_t carry=0;
  for(int i=0;i<LDE_SMALL_WORDS;++i) {uint64_t t=(uint64_t)b->w[i]*multiplier+a->w[i]+carry;a->w[i]=(uint32_t)t;carry=t>>32;}
}
static void lde_ssub(lde_small *a,const lde_small *b) {
  uint64_t borrow=0;
  for(int i=0;i<LDE_SMALL_WORDS;++i) {uint64_t t=(uint64_t)b->w[i]+borrow,x=a->w[i];a->w[i]=(uint32_t)(x-t);borrow=x<t;}
}
static int lde_ecmp(const lde_exact *a,const lde_exact *b) {
  for(int i=LDE_EXACT_WORDS-1;i>=0;--i)if(a->w[i]!=b->w[i])return a->w[i]>b->w[i]?1:-1;
  return 0;
}
static lde_exact lde_power(const ld_value *a,int degree) {
  ldn_wide square=ldn_product(a,a);lde_exact out={{0}};
  if(degree==2) {
    for(int i=0;i<LDN_WORDS*32;++i)if(ldn_wbit(&square,i)) {
      int j=i-LD_BASE;out.w[j/32]|=UINT32_C(1)<<(j%32);
    }
  } else {
    int at=ld_top(a)/32,bt=ldn_wtop(&square)/32;
    for(int i=0;i<=at;++i)if(a->w[i]) {
      uint64_t carry=0;
      for(int j=0;j<=bt;++j) {uint64_t t=(uint64_t)a->w[i]*square.w[j]+out.w[i+j]+carry;out.w[i+j]=(uint32_t)t;carry=t>>32;}
      out.w[i+bt+1]=(uint32_t)carry;
    }
  }
  return out;
}
/* Compare (left+right)^degree with radicand*2^degree. The sum is
 * deliberately never halved on the foundation grid: a minimum-subnormal
 * midpoint's low bit must survive the square or cube. */
static int lde_midcmp(const ldn_wide *radicand,const ld_value *left,const ld_value *right,int degree) {
  ld_value sum=*left;ld_add(&sum,right);
  lde_exact power=lde_power(&sum,degree),target={{0}};
  for(int i=0;i<LDN_WORDS*32;++i)if(ldn_wbit(radicand,i)) {
    int j=i-LD_BASE+degree;target.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  return lde_ecmp(&power,&target);
}
static int lde_rootcmp(const ldn_wide *radicand,const ld_value *candidate,int degree) {
  lde_exact power=lde_power(candidate,degree),target={{0}};
  for(int i=0;i<LDN_WORDS*32;++i)if(ldn_wbit(radicand,i)) {
    int j=i-LD_BASE;target.w[j/32]|=UINT32_C(1)<<(j%32);
  }
  return lde_ecmp(&power,&target);
}
static ld_raw lde_neighbor(unsigned fmt,const ld_value *a,int direction) {
  return fmt==106?lds_dd(a,direction):lds_single_neighbor(fmt,a,direction);
}
static ld_raw lde_root(unsigned fmt,const ldn_wide *radicand,int degree,int sign) {
  int top=ldn_wtop(radicand)+LDN_BASE;
  int exponent=top/degree;if(top<0 && top%degree)--exponent;
  int p=fmt==64?53:fmt==80?64:113;
  int cut=fmt==106?-1076:exponent-p-3;
  if(cut<LD_BASE)cut=LD_BASE;
  /* DD's lowest component is 2^-1074; its largest root exponent is1024.
   * Consequently at most2101 restoring digits are required, and a cube's
   * square/residual uses fewer than4208 bits. 216 limbs is a strict bound. */
  lde_small root={{0}},square={{0}},remainder={{0}};
  for(int position=exponent;position>=cut;--position) {
    lde_sshift(&remainder,(unsigned)degree);
    for(int j=0;j<degree;++j)remainder.w[0]|=(unsigned)ldn_wbit(radicand,degree*position+j-LDN_BASE)<<j;
    lde_small trial={{0}};trial.w[0]=1;
    if(degree==2)lde_sadd(&trial,&root,4);
    else {lde_sadd(&trial,&square,12);lde_sadd(&trial,&root,6);}
    int take=lde_scmp(&remainder,&trial)>=0;
    if(take)lde_ssub(&remainder,&trial);
    if(degree==3) {lde_sshift(&square,2);if(take) {lde_sadd(&square,&root,4);++square.w[0];}}
    lde_sshift(&root,1);root.w[0]|=(unsigned)take;
  }
  ld_value approximation={{0},0,LD_FINITE,0};
  for(int i=0;i<LDE_SMALL_WORDS*32;++i)if((root.w[i/32]>>(i%32))&1)ld_set(&approximation,i+cut-LD_BASE);
  ld_raw raw=fmt==106?lds_dd(&approximation,0):ld_pack(fmt,&approximation);
  ld_value selected=ld_decode(fmt,raw);
  if(selected.kind==LD_INF)selected=ld_decode(fmt,lds_limit(fmt,0));
  int cmp=lde_rootcmp(radicand,&selected,degree),exact=cmp==0;
  if(!exact) {
    ld_value left=selected,right=selected;
    if(cmp<0)right=ld_decode(fmt,lde_neighbor(fmt,&selected,1));
    else left=ld_decode(fmt,lde_neighbor(fmt,&selected,-1));
    /* A hypothetical value above the finite maximum supplies the final
     * overflow midpoint, without treating infinity as a finite endpoint. */
    if(right.kind==LD_INF) {
      right=left;ld_value gap={{0},0,LD_FINITE,0};
      int spacing=fmt==106?917:(fmt==64?1023:16383)-p+1;
      ld_insert(&gap,1,spacing);ld_add(&right,&gap);
    }
    int midpoint=lde_midcmp(radicand,&left,&right,degree);
    ld_value gap=lds_difference(right,left);
    selected=midpoint<0 || (midpoint==0 && ld_bit(&left,ld_top(&gap)))?right:left;
  }
  selected.sign=sign;raw=fmt==106?lds_dd(&selected,0):ld_pack(fmt,&selected);
  ld_value rounded=ld_decode(fmt,raw);
  lds_flags(fmt,raw,rounded.kind==LD_INF,!exact,0);return raw;
}
#endif
