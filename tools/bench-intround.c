/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired integer-return calls, common valid inputs and width-safe large values.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/basic.h>
#include <fenv.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
static double doubles[N];static float floats[N];static volatile uint64_t sink;
static uint32_t state=0x696e7472u;
static uint32_t random_word(void) {state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static int seeded;
#define MEASURE(NAME,ARG,RESULT,INPUTS) \
static double NAME(RESULT (*volatile function)(ARG)) { \
  if (feclearexcept(FE_ALL_EXCEPT)||(seeded&&feraiseexcept(FE_INEXACT))) exit(2); \
  struct timespec start,end;uint64_t checksum=0; \
  if (fetestexcept(FE_ALL_EXCEPT)!=(seeded?FE_INEXACT:0)||clock_gettime(CLOCK_MONOTONIC,&start)) exit(2); \
  for (int i=0;i<N;++i) checksum+=(uint64_t)function(INPUTS[i]); \
  if (clock_gettime(CLOCK_MONOTONIC,&end)) exit(2); \
  double elapsed=((double)(end.tv_sec-start.tv_sec)*1e9+(double)(end.tv_nsec-start.tv_nsec))/N; \
  sink=checksum;return elapsed; \
}
MEASURE(measure_long,double,long,doubles)
MEASURE(measure_longf,float,long,floats)
MEASURE(measure_ll,double,long long,doubles)
MEASURE(measure_llf,float,long long,floats)
static double measure(unsigned api,int host) {
  switch (api) {
  case 0:return measure_long(host?lround:gmath_lround);
  case 1:return measure_longf(host?lroundf:gmath_lroundf);
  case 2:return measure_ll(host?llround:gmath_llround);
  default:return measure_llf(host?llroundf:gmath_llroundf);
  }
}
static int64_t result(unsigned api,int host,int index) {
  switch (api) {
  case 0:{long (*volatile fn)(double)=host?lround:gmath_lround;return fn(doubles[index]);}
  case 1:{long (*volatile fn)(float)=host?lroundf:gmath_lroundf;return fn(floats[index]);}
  case 2:{long long (*volatile fn)(double)=host?llround:gmath_llround;return fn(doubles[index]);}
  default:{long long (*volatile fn)(float)=host?llroundf:gmath_llroundf;return fn(floats[index]);}
  }
}
static void verify(unsigned api) {
  double limit=(api>=2||LONG_MAX==INT64_MAX)?0x1p63:0x1p31;
  for (int i=0;i<N;++i) {
    double x=(api&1u)?(double)floats[i]:doubles[i];
    if (!(x>-limit&&x<limit)) {fputs("benchmark input outside strict destination bounds\n",stderr);exit(2);}
    if (feclearexcept(FE_ALL_EXCEPT)) exit(2);
    int64_t a=result(api,0,i);if (fetestexcept(FE_INVALID)) exit(2);
    if (feclearexcept(FE_ALL_EXCEPT)) exit(2);
    int64_t b=result(api,1,i);if (fetestexcept(FE_INVALID)||a!=b) {fputs("benchmark result/range control differs\n",stderr);exit(2);}
  }
}
static int compare(const void * a,const void * b) {double x=*(const double *)a,y=*(const double *)b;return (x>y)-(x<y);}
static void population(unsigned api,unsigned range) {
  for (int i=0;i<N;++i) {
    uint32_t raw=random_word();double d;float f;
    if (range==0) {d=((double)(raw&0xffffu)-32768.0)*0.125;f=(float)d;}
    else if (range==1) {d=(double)(raw%2001u)-1000.0+0.5;f=(float)d;}
    else if (range==2) {
      uint64_t word=((uint64_t)(raw>>31)<<63)|(uint64_t)(raw&0x7fffffu);memcpy(&d,&word,8);
      uint32_t wordf=(raw&0x807fffffu)|1u;memcpy(&f,&wordf,4);
    } else {
      unsigned wide=api>=2||LONG_MAX==INT64_MAX;
      uint64_t word=((uint64_t)(raw>>31)<<63)|(wide?UINT64_C(0x43d0000000000000):UINT64_C(0x41d0000000000000))|((uint64_t)(raw&0x7fffffu)<<29);memcpy(&d,&word,8);
      uint32_t wordf=(raw&0x807fffffu)|(wide?0x5e800000u:0x4e800000u);memcpy(&f,&wordf,4);
    }
    doubles[i]=d;floats[i]=f;
  }
}
int main(void) {
  if (fesetenv(FE_DFL_ENV)||fesetround(FE_TONEAREST)) return 2;
  const char * apis[]={"lround","lroundf","llround","llroundf"};
  const char * ranges[]={"common","ties","subnormal","wide valid"};
  printf("integer rounding: native long %u bits, 401 alternating pairs of %d inputs; indirect calls include loop/checksum overhead\n",LONG_MAX==INT32_MAX?32u:64u,N);
  for (unsigned api=0;api<4;++api) for (seeded=0;seeded<2;++seeded) for (unsigned range=0;range<4;++range) {
    population(api,range);verify(api);
    for (unsigned warm=0;warm<10;++warm) {(void)measure(api,0);(void)measure(api,1);}
    double ratios[401],candidate[401],host[401];
    for (unsigned i=0;i<401;++i) {
      double a,b;if (i&1u) {b=measure(api,1);a=measure(api,0);}else {a=measure(api,0);b=measure(api,1);}
      candidate[i]=a;host[i]=b;ratios[i]=a/b;
    }
    qsort(ratios,401,sizeof *ratios,compare);
    qsort(candidate,401,sizeof *candidate,compare);qsort(host,401,sizeof *host,compare);
    printf("%-8s %-10s %-7s flags gmath %.3f ns libm %.3f ns median %.3fx p10-p90 %.3f..%.3fx\n",apis[api],ranges[range],seeded?"IX":"clean",candidate[200],host[200],ratios[200],ratios[40],ratios[360]);
  }
  return 0;
}
