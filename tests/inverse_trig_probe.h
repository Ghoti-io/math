/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared raw numerical/state probe for all four inverse circular additions.
 */
#ifndef GMATH_INVERSE_TRIG_PROBE_H
#define GMATH_INVERSE_TRIG_PROBE_H
#include <ghoti.io/math/elementary.h>
#include "fp_controls.h"
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t it_bits(double x) {uint64_t u;memcpy(&u,&x,8);return u;}
static double it_double(uint64_t u) {double x;memcpy(&x,&u,8);return x;}
static uint32_t it_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float it_float(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static double it_value(uint64_t u,unsigned width) {
  return width==64 ? it_double(u) : (double)it_float((uint32_t)u);
}
static int it_flags(unsigned f) {
  return ((f&1u)?FE_INVALID:0)|((f&2u)?FE_INEXACT:0)|((f&4u)?FE_UNDERFLOW:0)|
      ((f&8u)?FE_OVERFLOW:0)|((f&16u)?FE_DIVBYZERO:0);
}
static uint64_t it_call(uint64_t x,unsigned width,unsigned cosine) {
  if(width==64) {
    double (*volatile fn)(double)=cosine?gmath_acos:gmath_asin;
    return it_bits(fn(it_double(x)));
  }
  float (*volatile fn)(float)=cosine?gmath_acosf:gmath_asinf;
  return it_fbits(fn(it_float((uint32_t)x)));
}
static unsigned it_expected_flags(uint64_t x,unsigned width,unsigned cosine) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1);
  uint64_t inf=(uint64_t)(2*bias+1)<<p,one=(uint64_t)bias<<p;
  if(a>inf)return (a&(UINT64_C(1)<<(p-1)))?0u:1u;
  if(a>one)return 1;
  if((!cosine&&!a)||(cosine&&x==one))return 0;
  return 2u|((!cosine&&a<(UINT64_C(1)<<p))?4u:0u);
}
static int it_strict(uint64_t x,unsigned width,unsigned cosine) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1),one=(uint64_t)bias<<p;
  uint64_t tiny=(uint64_t)(bias-(cosine?(width==64?60:28):(width==64?30:12)))<<p;
  return a>=one || a<tiny;
}
static int it_selected(uint64_t x,unsigned width,unsigned row) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t a=x&((UINT64_C(1)<<(width-1))-1);
  const uint64_t centers[]={(uint64_t)(bias-1)<<p,
      (uint64_t)(bias-(width==64?30:12))<<p,
      (uint64_t)(bias-(width==64?60:28))<<p};
  for(unsigned i=0;i<3;++i)if(a>=centers[i]-8&&a<=centers[i]+8)return 1;
  return row%97==0;
}
static double it_power(int e) {
  return it_double(e>=-1022?(uint64_t)(e+1023)<<52:UINT64_C(1)<<(e+1074));
}
static int it_accuracy(uint64_t got,uint64_t target,unsigned width,int64_t low,int64_t high,double *maximum) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=target&(sign-1),inf=(uint64_t)(2*bias+1)<<p;
  if(a>=inf||!a)return got!=target;
  if((got&(sign-1))>=inf)return 1;
  int exponent=(int)(a>>p)-(int)bias-(int)p;
  if(exponent<1-(int)bias-(int)p)exponent=1-(int)bias-(int)p;
  double delta=(it_value(got,width)-it_value(target,width))/it_power(exponent);
  double left=delta-(double)low/0x1p30,right=delta-(double)high/0x1p30;
  if(left<0)left=-left;
  if(right<0)right=-right;
  double error=left>right?left:right;
  /* If the real answer lies below a binade endpoint, its spacing is half
   * the spacing used for the stored residual. Avoid a factor-two loophole. */
  int towardzero=target&sign ? high>0 : low<0;
  double limit=(!(a&((UINT64_C(1)<<p)-1))&&a>(UINT64_C(1)<<p)&&towardzero)?0.5:1.0;
  double normalized=error/limit;
  if(normalized>*maximum)*maximum=normalized;
  return !(error<=limit);
}
static uint64_t it_hash(uint64_t hash,uint64_t word) {
  for(unsigned i=0;i<8;++i){hash^=(unsigned char)(word>>(8*i));hash*=UINT64_C(1099511628211);}
  return hash;
}
/* Return nonzero on malformed/reference/numerical/state failure. No rows or
 * incomplete final lines are accepted. SHA verification is an independent gate.
 */
static int inverse_trig_probe(const char *directory,int state,int print_hashes) {
  char path[4096],line[512];FILE *file=NULL;fenv_t saved;int saved_errno=errno,status=1;
  uint64_t hashes[4]={UINT64_C(14695981039346656037),UINT64_C(14695981039346656037),
                     UINT64_C(14695981039346656037),UINT64_C(14695981039346656037)};
  unsigned long counts[4]={0,0,0,0},rows=0;double maximum[4]={0,0,0,0};
  unsigned error_width=0,error_cosine=0;uint64_t error_input=0,error_target=0,error_got=0;
  int error_mode=FE_TONEAREST;
  if(fegetenv(&saved)||snprintf(path,sizeof path,"%s/inverse-trig.corpus",directory)>=(int)sizeof path)return 1;
  file=fopen(path,"rb");if(!file)goto finish;
  if(!fgets(line,sizeof line,file)||strncmp(line,"# inverse-trig-v1 seed=",23))goto finish;
  if(!fgets(line,sizeof line,file)||strncmp(line,"# width input ",14))goto finish;
  while(fgets(line,sizeof line,file)) {
    gmath_inverse_row row;
    error_width=0;
    ++rows;
    if(rows>100000||gmath_parse_inverse_row(line,&row))goto finish;
    unsigned width=row.width;uint64_t x=row.input;
    const uint64_t *target=row.target;const unsigned *flags=row.flags;
    const int64_t *low=row.low,*high=row.high;
    for(unsigned cosine=0;cosine<2;++cosine) {
      unsigned index=(width==64?0:2)+cosine;
      error_width=width;error_cosine=cosine;error_input=x;error_target=target[cosine];error_mode=FE_TONEAREST;
      if(flags[cosine]!=it_expected_flags(x,width,cosine)||low[cosine]>high[cosine]||
          low[cosine]<-536870913LL||high[cosine]>536870913LL)goto finish;
      if(fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT))goto finish;
      errno=733;uint64_t controls=gmath_test_controls(),got=it_call(x,width,cosine);error_got=got;
      if(fetestexcept(FE_ALL_EXCEPT)!=it_flags(flags[cosine])||errno!=733||
          fegetround()!=FE_TONEAREST||gmath_test_controls()!=controls)goto finish;
      if(it_accuracy(got,target[cosine],width,low[cosine],high[cosine],&maximum[index])||
          (it_strict(x,width,cosine)&&got!=target[cosine]))goto finish;
      hashes[index]=it_hash(hashes[index],width==64?got:it_bits(it_value(got,32)));++counts[index];
      if(state&&(it_selected(x,width,(unsigned)rows)||it_strict(x,width,cosine))) {
        const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
        for(unsigned m=0;m<4;++m)for(unsigned subset=0;subset<32;++subset) {
          if(fesetround(modes[m])||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(it_flags(subset)))goto finish;
          int incoming=fetestexcept(FE_ALL_EXCEPT);controls=gmath_test_controls();errno=991;
          got=it_call(x,width,cosine);error_got=got;error_mode=modes[m];
          if(fetestexcept(FE_ALL_EXCEPT)!=(incoming|it_flags(flags[cosine]))||errno!=991||
              fegetround()!=modes[m]||gmath_test_controls()!=controls||
              (it_strict(x,width,cosine)&&got!=target[cosine]))goto finish;
        }
      }
    }
  }
  if(ferror(file)||!rows||!counts[0]||!counts[2])goto finish;
  if(print_hashes) {
    const char *names[]={"asin","acos","asinf","acosf"};
    for(unsigned i=0;i<4;++i)printf("math.%s.hash %016llx\nmath.%s.count %lu\n",
        names[i],(unsigned long long)hashes[i],names[i],counts[i]);
  } else printf("inverse-trig: %lu rows; closed sampled ULP bounds %.9f %.9f %.9f %.9f\n",
      rows,maximum[0],maximum[1],maximum[2],maximum[3]);
  status=0;
finish:
  if(status) {
    fprintf(stderr,"inverse-trig: rejected at row %lu in %s\n",rows,path);
    if(error_width)fprintf(stderr,"  %s%u input=%016llx target=%016llx got=%016llx mode=%d\n",
        error_cosine?"acos":"asin",error_width,(unsigned long long)error_input,
        (unsigned long long)error_target,(unsigned long long)error_got,error_mode);
  }
  if(file)fclose(file);
  if(fesetenv(&saved))status=1;
  errno=saved_errno;return status;
}
#endif
