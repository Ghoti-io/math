/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared raw numerical/state probe for all six inverse hyperbolic additions.
 */
#ifndef GMATH_INVERSE_HYPERBOLIC_PROBE_H
#define GMATH_INVERSE_HYPERBOLIC_PROBE_H
#include <ghoti.io/math/elementary.h>
#include "fp_controls.h"
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t ip_bits(double x) {uint64_t u;memcpy(&u,&x,8);return u;}
static double ip_double(uint64_t u) {double x;memcpy(&x,&u,8);return x;}
static uint32_t ip_fbits(float x) {uint32_t u;memcpy(&u,&x,4);return u;}
static float ip_float(uint32_t u) {float x;memcpy(&x,&u,4);return x;}
static double ip_value(uint64_t u,unsigned width) {
  return width==64 ? ip_double(u) : (double)ip_float((uint32_t)u);
}
static int ip_flags(unsigned f) {
  return ((f&1u)?FE_INVALID:0)|((f&2u)?FE_INEXACT:0)|((f&4u)?FE_UNDERFLOW:0)|
      ((f&8u)?FE_OVERFLOW:0)|((f&16u)?FE_DIVBYZERO:0);
}
static uint64_t ip_call(uint64_t x,unsigned width,unsigned kind) {
  if(width==64) {
    double (*volatile fn)(double)=kind==0?gmath_asinh:kind==1?gmath_acosh:gmath_atanh;
    return ip_bits(fn(ip_double(x)));
  }
  float (*volatile fn)(float)=kind==0?gmath_asinhf:kind==1?gmath_acoshf:gmath_atanhf;
  return ip_fbits(fn(ip_float((uint32_t)x)));
}
static unsigned ip_expected_flags(uint64_t x,unsigned width,unsigned kind) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1),inf=(uint64_t)(2*bias+1)<<p,one=(uint64_t)bias<<p;
  if(a>inf)return (a&(UINT64_C(1)<<(p-1)))?0u:1u;
  if(kind==1) {
    if(x&sign||a<one)return 1;
    return a==one||a==inf?0u:2u;
  }
  if(kind==2&&a>=one)return a==one?16u:1u;
  if(!a||a==inf)return 0;
  return 2u|(a<(UINT64_C(1)<<p)?4u:0u);
}
static int ip_strict(uint64_t x,unsigned width,unsigned kind) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1),inf=(uint64_t)(2*bias+1)<<p,one=(uint64_t)bias<<p;
  if(a>=inf)return 1;
  if(kind==1)return (x&sign)||a<=one;
  return (kind==2&&a>=one)||a<((uint64_t)(bias-(width==64?60:26))<<p);
}
static int ip_sanity(uint64_t got,uint64_t x,unsigned width,unsigned kind) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=x&(sign-1),out=got&(sign-1);
  uint64_t inf=(uint64_t)(2*bias+1)<<p,one=(uint64_t)bias<<p;
  if(a>=inf||(kind==1&&((x&sign)||a<one))||(kind==2&&a>=one))return 0;
  if(out>=inf)return 1;
  if(kind==1)return (got&sign)!=0||(a>one&&!out);
  return (got&sign)!=(x&sign)||(a&&!out);
}
static int ip_selected(uint64_t x,unsigned width,unsigned row) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t a=x&((UINT64_C(1)<<(width-1))-1);
  const uint64_t centers[]={(uint64_t)(bias-1)<<p,(uint64_t)bias<<p,(uint64_t)(bias+1)<<p,
      (uint64_t)(bias-(width==64?60:26))<<p,(uint64_t)(bias+60)<<p,
      width==64?UINT64_C(0x3fdaaaaaaaaaaaab):UINT64_C(0x3ed55555),
      width==64?UINT64_C(0x3ff1555555555555):UINT64_C(0x3f8aaaab),
      width==64?UINT64_C(0x3fc999999999999a):UINT64_C(0x3e4ccccd)};
  for(unsigned i=0;i<sizeof centers/sizeof *centers;++i)if(a>=centers[i]-16&&a<=centers[i]+16)return 1;
  uint64_t inf=(uint64_t)(2*bias+1)<<p;
  return a>=inf-16 || row%97==0;
}
static int ip_accuracy(uint64_t got,uint64_t target,unsigned width,int64_t low,int64_t high,double *maximum) {
  unsigned p=width==64?52:23,bias=width==64?1023:127;
  uint64_t sign=UINT64_C(1)<<(width-1),a=target&(sign-1),inf=(uint64_t)(2*bias+1)<<p;
  if(a>=inf||!a)return got!=target;
  if((got&(sign-1))>=inf)return 1;
  uint64_t b=got&(sign-1),distance=a>b?a-b:b-a;
  int power=!(a&((UINT64_C(1)<<p)-1))&&a>(UINT64_C(1)<<p);
  if(((got^target)&sign)&&b)return 1;
  if(distance>1 && !(power&&b<a&&distance==2))return 1;
  /* Adjacent words differ by exactly one target ULP, except the half-step
   * below a normal power of two. Integer ranks avoid subnormal arithmetic
   * and remain exact with both DAZ and FTZ enabled. */
  double delta=(double)distance*(b<a?-1.0:1.0);
  if(power&&b<a)delta*=0.5;
  if(target&sign)delta=-delta;
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
static uint64_t ip_hash(uint64_t hash,uint64_t word) {
  for(unsigned i=0;i<8;++i){hash^=(unsigned char)(word>>(8*i));hash*=UINT64_C(1099511628211);}
  return hash;
}
/* Return nonzero on malformed/reference/numerical/state failure. Empty corpora and
 * incomplete final lines are rejected. Complete population/SHA belongs to the family gate.
 */
static int inverse_hyperbolic_probe(const char *directory,int state,int print_hashes) {
  char path[4096],line[512];FILE *file=NULL;fenv_t saved;int saved_errno=errno,status=1;
  uint64_t hashes[6];for(unsigned i=0;i<6;++i)hashes[i]=UINT64_C(14695981039346656037);
  unsigned long counts[6]={0,0,0,0,0,0},rows=0;double maximum[6]={0,0,0,0,0,0};
  unsigned error_width=0,error_kind=0;uint64_t error_input=0,error_target=0,error_got=0;
  uint64_t maximum_input[6]={0,0,0,0,0,0},maximum_target[6]={0,0,0,0,0,0},maximum_got[6]={0,0,0,0,0,0};
  int64_t maximum_low[6]={0,0,0,0,0,0},maximum_high[6]={0,0,0,0,0,0};
  int error_mode=FE_TONEAREST,error_actual_mode=FE_TONEAREST,error_errno=0;
  unsigned error_subset=0;int error_expected_flags=0,error_actual_flags=0;
  uint64_t error_controls=0,error_actual_controls=0;const char *error_stage="loader";
  if(fegetenv(&saved)||snprintf(path,sizeof path,"%s/inverse-hyperbolic.corpus",directory)>=(int)sizeof path)return 1;
  file=fopen(path,"rb");if(!file)goto finish;
  if(!fgets(line,sizeof line,file)||strncmp(line,"# inverse-hyperbolic-v1 seed=",sizeof("# inverse-hyperbolic-v1 seed=")-1))goto finish;
  if(!fgets(line,sizeof line,file)||strcmp(line,"# width input asinh-target/flags/residual-low/high acosh-target/flags/residual-low/high atanh-target/flags/residual-low/high; residual scale=2^30 ULP\n"))goto finish;
  while(fgets(line,sizeof line,file)) {
    gmath_hyperbolic_row row;
    error_width=0;error_stage="loader";
    ++rows;
    if(rows>100000||gmath_parse_hyperbolic_row(line,&row))goto finish;
    unsigned width=row.width;uint64_t x=row.input;
    const uint64_t *target=row.target;const unsigned *flags=row.flags;
    const int64_t *low=row.low,*high=row.high;
    for(unsigned kind=0;kind<3;++kind) {
      unsigned index=(width==64?0:3)+kind;
      error_width=width;error_kind=kind;error_input=x;error_target=target[kind];error_mode=FE_TONEAREST;
      error_stage="reference";
      if(flags[kind]!=ip_expected_flags(x,width,kind)||low[kind]>high[kind]||
          low[kind]<-536870913LL||high[kind]>536870913LL)goto finish;
      if(fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT))goto finish;
      errno=733;uint64_t controls=gmath_test_controls(),got=ip_call(x,width,kind);error_got=got;
      error_stage="state";error_subset=0;error_expected_flags=ip_flags(flags[kind]);
      error_actual_flags=fetestexcept(FE_ALL_EXCEPT);error_errno=errno;error_actual_mode=fegetround();
      error_controls=controls;error_actual_controls=gmath_test_controls();
      if(error_actual_flags!=error_expected_flags||error_errno!=733||
          error_actual_mode!=FE_TONEAREST||error_actual_controls!=controls)goto finish;
      error_stage="accuracy";
      double previous_maximum=maximum[index];
      int inaccurate=ip_accuracy(got,target[kind],width,low[kind],high[kind],&maximum[index]);
      if(maximum[index]>previous_maximum||!counts[index]) {
        maximum_input[index]=x;maximum_target[index]=target[kind];maximum_got[index]=got;
        maximum_low[index]=low[kind];maximum_high[index]=high[kind];
      }
      if(inaccurate)goto finish;
      error_stage="special";
      if(ip_strict(x,width,kind)&&got!=target[kind])goto finish;
      error_stage="sanity";if(ip_sanity(got,x,width,kind))goto finish;
      hashes[index]=ip_hash(hashes[index],width==64?got:ip_bits(ip_value(got,32)));++counts[index];
      if(state&&(ip_selected(x,width,(unsigned)rows)||ip_strict(x,width,kind))) {
        const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
        for(unsigned m=0;m<4;++m)for(unsigned subset=0;subset<32;++subset) {
          if(fesetround(modes[m])||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(ip_flags(subset)))goto finish;
          int incoming=fetestexcept(FE_ALL_EXCEPT);controls=gmath_test_controls();errno=991;
          got=ip_call(x,width,kind);error_got=got;error_mode=modes[m];
          error_stage="state";error_subset=subset;error_expected_flags=incoming|ip_flags(flags[kind]);
          error_actual_flags=fetestexcept(FE_ALL_EXCEPT);error_errno=errno;error_actual_mode=fegetround();
          error_controls=controls;error_actual_controls=gmath_test_controls();
          if(error_actual_flags!=error_expected_flags||error_errno!=991||
              error_actual_mode!=modes[m]||error_actual_controls!=controls)goto finish;
          error_stage="special";
          if(ip_strict(x,width,kind)&&got!=target[kind])goto finish;
          error_stage="sanity";if(ip_sanity(got,x,width,kind))goto finish;
        }
      }
    }
  }
  if(ferror(file)||!rows||!counts[0]||!counts[3])goto finish;
  if(fesetround(FE_TONEAREST))goto finish;
  if(print_hashes) {
    const char *names[]={"asinh","acosh","atanh","asinhf","acoshf","atanhf"};
    for(unsigned i=0;i<6;++i)printf("math.%s.hash %016llx\nmath.%s.count %lu\n",
        names[i],(unsigned long long)hashes[i],names[i],counts[i]);
  } else {
    printf("inverse-hyperbolic: loaded %s\n",path);
    const char *names[]={"asinh","acosh","atanh","asinhf","acoshf","atanhf"};
    for(unsigned i=0;i<6;++i)printf("inverse-hyperbolic: maximum %s input=%016llx target=%016llx got=%016llx low=%lld high=%lld bound=%a approx=%.17g\n",
        names[i],(unsigned long long)maximum_input[i],(unsigned long long)maximum_target[i],
        (unsigned long long)maximum_got[i],(long long)maximum_low[i],(long long)maximum_high[i],maximum[i],maximum[i]);
    printf("inverse-hyperbolic: %lu rows; closed sampled ULP bounds",rows);
    for(unsigned i=0;i<6;++i)printf(" %a",maximum[i]);
    printf("\n");
  }
  status=0;
finish:
  if(status) {
    fprintf(stderr,"inverse-hyperbolic: rejected at row %lu in %s\n",rows,path);
    fprintf(stderr,"  stage=%s subset=%u flags-expected=%x observed=%x errno=%d controls-expected=%016llx observed=%016llx mode-expected=%d observed=%d\n",
        error_stage,error_subset,error_expected_flags,error_actual_flags,error_errno,
        (unsigned long long)error_controls,(unsigned long long)error_actual_controls,error_mode,error_actual_mode);
    if(error_width)fprintf(stderr,"  %s%u input=%016llx target=%016llx got=%016llx mode=%d\n",
        error_kind==0?"asinh":error_kind==1?"acosh":"atanh",error_width,(unsigned long long)error_input,
        (unsigned long long)error_target,(unsigned long long)error_got,error_mode);
  }
  if(file)fclose(file);
  if(fesetenv(&saved))status=1;
  errno=saved_errno;return status;
}
#endif
