/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared raw numerical/state probe for all four cancellation-safe additions.
 */
#ifndef GMATH_LOG1P_EXPM1_PROBE_H
#define GMATH_LOG1P_EXPM1_PROBE_H
#include <ghoti.io/math/elementary.h>
#include "fp_controls.h"
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t pe_bits(double x) {uint64_t u;memcpy(&u,&x,8);return u;}
static double pe_double(uint64_t u) {double x;memcpy(&x,&u,8);return x;}
static uint32_t pe_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float pe_float(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static double pe_value(uint64_t u,unsigned width) {
  return width==64 ? pe_double(u) : (double)pe_float((uint32_t)u);
}
static int pe_flags(unsigned f) {
  return ((f&1u)?FE_INVALID:0)|((f&2u)?FE_INEXACT:0)|((f&4u)?FE_UNDERFLOW:0)|
      ((f&8u)?FE_OVERFLOW:0)|((f&16u)?FE_DIVBYZERO:0);
}
static uint64_t pe_call(uint64_t x,unsigned width,unsigned exponential) {
  if(width==64) {
    double (*volatile fn)(double)=exponential?gmath_expm1:gmath_log1p;
    return pe_bits(fn(pe_double(x)));
  }
  float (*volatile fn)(float)=exponential?gmath_expm1f:gmath_log1pf;
  return pe_fbits(fn(pe_float((uint32_t)x)));
}
static unsigned pe_expected_flags(uint64_t x,unsigned width,unsigned exponential) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1);
  uint64_t inf=(uint64_t)(2*bias+1)<<p,one=(uint64_t)bias<<p;
  if(a>inf)return (a&(UINT64_C(1)<<(p-1)))?0u:1u;
  if(!a)return 0;
  if(exponential) {
    if(a==inf)return 0;
    uint64_t cut=width==64?UINT64_C(0x40862e42fefa39f0):UINT64_C(0x42b17218);
    if(!(x&sign)&&x>=cut)return 10;
  } else {
    if(x==(sign|one))return 16;
    if((x&sign)&&a>one)return 1;
    if(a==inf)return 0;
  }
  return 2u|(a<(UINT64_C(1)<<p)?4u:0u);
}
static int pe_strict(uint64_t x,unsigned width,unsigned exponential) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1),inf=(uint64_t)(2*bias+1)<<p;
  uint64_t tiny=(uint64_t)(bias-(width==64?60:26))<<p;
  if(a>=inf||a<tiny)return 1;
  if(exponential) {
    uint64_t cut=width==64?UINT64_C(0x40862e42fefa39f0):UINT64_C(0x42b17218);
    uint64_t saturation=width==64?UINT64_C(0x4044000000000000):UINT64_C(0x41a00000);
    return x&sign?a>=saturation:x>=cut;
  }
  return (x&sign)&&a>=((uint64_t)bias<<p);
}
static int pe_selected(uint64_t x,unsigned width,unsigned row) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t a=x&((UINT64_C(1)<<(width-1))-1);
  const uint64_t centers[]={(uint64_t)(bias-1)<<p,(uint64_t)bias<<p,
      (uint64_t)(bias-(width==64?60:26))<<p,(uint64_t)(bias+60)<<p,
      width==64?UINT64_C(0x4044000000000000):UINT64_C(0x41a00000),
      width==64?UINT64_C(0x40862e42fefa39f0):UINT64_C(0x42b17218),
      width==64?UINT64_C(0x4042b708872320e2):UINT64_C(0x418aa123)};
  for(unsigned i=0;i<sizeof centers/sizeof *centers;++i)if(a>=centers[i]-16&&a<=centers[i]+16)return 1;
  uint64_t inf=(uint64_t)(2*bias+1)<<p;
  return a>=inf-16 || row%97==0;
}
static double pe_power(int e) {
  return pe_double(e>=-1022?(uint64_t)(e+1023)<<52:UINT64_C(1)<<(e+1074));
}
static int pe_accuracy(uint64_t got,uint64_t target,unsigned width,int64_t low,int64_t high,double *maximum) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=target&(sign-1),inf=(uint64_t)(2*bias+1)<<p;
  if(a>=inf||!a)return got!=target;
  if((got&(sign-1))>=inf)return 1;
  int exponent=(int)(a>>p)-(int)bias-(int)p;
  if(exponent<1-(int)bias-(int)p)exponent=1-(int)bias-(int)p;
  double delta=(pe_value(got,width)-pe_value(target,width))/pe_power(exponent);
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
static uint64_t pe_hash(uint64_t hash,uint64_t word) {
  for(unsigned i=0;i<8;++i){hash^=(unsigned char)(word>>(8*i));hash*=UINT64_C(1099511628211);}
  return hash;
}
/* Return nonzero on malformed/reference/numerical/state failure. Empty corpora or
 * incomplete final lines are accepted. SHA verification is an independent gate.
 */
static int log1p_expm1_probe(const char *directory,int state,int print_hashes) {
  char path[4096],line[512];FILE *file=NULL;fenv_t saved;int saved_errno=errno,status=1;
  uint64_t hashes[4]={UINT64_C(14695981039346656037),UINT64_C(14695981039346656037),
                     UINT64_C(14695981039346656037),UINT64_C(14695981039346656037)};
  unsigned long counts[4]={0,0,0,0},rows=0;double maximum[4]={0,0,0,0};
  unsigned error_width=0,error_exponential=0;uint64_t error_input=0,error_target=0,error_got=0;
  uint64_t maximum_input[4]={0,0,0,0},maximum_target[4]={0,0,0,0},maximum_got[4]={0,0,0,0};
  int64_t maximum_low[4]={0,0,0,0},maximum_high[4]={0,0,0,0};
  int error_mode=FE_TONEAREST;
  if(fegetenv(&saved)||snprintf(path,sizeof path,"%s/log1p-expm1.corpus",directory)>=(int)sizeof path)return 1;
  file=fopen(path,"rb");if(!file)goto finish;
  if(!fgets(line,sizeof line,file)||strncmp(line,"# log1p-expm1-v1 seed=",22))goto finish;
  if(!fgets(line,sizeof line,file)||strncmp(line,"# width input ",14))goto finish;
  while(fgets(line,sizeof line,file)) {
    gmath_inverse_row row;
    error_width=0;
    ++rows;
    if(rows>100000||gmath_parse_inverse_row(line,&row))goto finish;
    unsigned width=row.width;uint64_t x=row.input;
    const uint64_t *target=row.target;const unsigned *flags=row.flags;
    const int64_t *low=row.low,*high=row.high;
    for(unsigned exponential=0;exponential<2;++exponential) {
      unsigned index=(width==64?0:2)+exponential;
      error_width=width;error_exponential=exponential;error_input=x;error_target=target[exponential];error_mode=FE_TONEAREST;
      if(flags[exponential]!=pe_expected_flags(x,width,exponential)||low[exponential]>high[exponential]||
          low[exponential]<-536870913LL||high[exponential]>536870913LL)goto finish;
      if(fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT))goto finish;
      errno=733;uint64_t controls=gmath_test_controls(),got=pe_call(x,width,exponential);error_got=got;
      if(fetestexcept(FE_ALL_EXCEPT)!=pe_flags(flags[exponential])||errno!=733||
          fegetround()!=FE_TONEAREST||gmath_test_controls()!=controls)goto finish;
      double previous_maximum=maximum[index];
      int inaccurate=pe_accuracy(got,target[exponential],width,low[exponential],high[exponential],&maximum[index]);
      if(maximum[index]>previous_maximum||!counts[index]) {
        maximum_input[index]=x;maximum_target[index]=target[exponential];maximum_got[index]=got;
        maximum_low[index]=low[exponential];maximum_high[index]=high[exponential];
      }
      if(inaccurate||
          (pe_strict(x,width,exponential)&&got!=target[exponential]))goto finish;
      hashes[index]=pe_hash(hashes[index],width==64?got:pe_bits(pe_value(got,32)));++counts[index];
      if(state&&(pe_selected(x,width,(unsigned)rows)||pe_strict(x,width,exponential))) {
        const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
        for(unsigned m=0;m<4;++m)for(unsigned subset=0;subset<32;++subset) {
          if(fesetround(modes[m])||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(pe_flags(subset)))goto finish;
          int incoming=fetestexcept(FE_ALL_EXCEPT);controls=gmath_test_controls();errno=991;
          got=pe_call(x,width,exponential);error_got=got;error_mode=modes[m];
          if(fetestexcept(FE_ALL_EXCEPT)!=(incoming|pe_flags(flags[exponential]))||errno!=991||
              fegetround()!=modes[m]||gmath_test_controls()!=controls||
              (pe_strict(x,width,exponential)&&got!=target[exponential]))goto finish;
        }
      }
    }
  }
  if(ferror(file)||!rows||!counts[0]||!counts[2])goto finish;
  if(print_hashes) {
    const char *names[]={"log1p","expm1","log1pf","expm1f"};
    for(unsigned i=0;i<4;++i)printf("math.%s.hash %016llx\nmath.%s.count %lu\n",
        names[i],(unsigned long long)hashes[i],names[i],counts[i]);
  } else {
    printf("log1p-expm1: loaded %s\n",path);
    const char *names[]={"log1p","expm1","log1pf","expm1f"};
    for(unsigned i=0;i<4;++i)printf("log1p-expm1: maximum %s input=%016llx target=%016llx got=%016llx low=%lld high=%lld bound=%.17g\n",
        names[i],(unsigned long long)maximum_input[i],(unsigned long long)maximum_target[i],
        (unsigned long long)maximum_got[i],(long long)maximum_low[i],(long long)maximum_high[i],maximum[i]);
    printf("log1p-expm1: %lu rows; closed sampled ULP bounds %.17g %.17g %.17g %.17g\n",
      rows,maximum[0],maximum[1],maximum[2],maximum[3]);
  }
  status=0;
finish:
  if(status) {
    fprintf(stderr,"log1p-expm1: rejected at row %lu in %s\n",rows,path);
    if(error_width)fprintf(stderr,"  %s%u input=%016llx target=%016llx got=%016llx mode=%d\n",
        error_exponential?"expm1":"log1p",error_width,(unsigned long long)error_input,
        (unsigned long long)error_target,(unsigned long long)error_got,error_mode);
  }
  if(file)fclose(file);
  if(fesetenv(&saved))status=1;
  errno=saved_errno;return status;
}
#endif
