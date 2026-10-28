/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired host timing; host output guards are not independent accuracy proofs.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/basic.h>
#include "../tests/current_ir_prior.h"
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
#define PAIRS 401
static double dx[N];
static float fx[N];
static volatile uint64_t sink;
static long (*volatile ld)(double);
static long (*volatile lf)(float);
static long long (*volatile lld)(double);
static long long (*volatile llf)(float);
static uint64_t tick(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC,&t)) {exit(2);}
  return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static uint64_t rng(uint64_t * s) {*s^=*s<<13;*s^=*s>>7;*s^=*s<<17;return *s;}
static uint64_t bits64(double x) {uint64_t w;memcpy(&w,&x,8);return w;}
static uint32_t bits32(float x) {uint32_t w;memcpy(&w,&x,4);return w;}
static int cmpu(const void * a,const void * b) {uint64_t x=*(const uint64_t *)a,y=*(const uint64_t *)b;return (x>y)-(x<y);}
static int cmpd(const void * a,const void * b) {double x=*(const double *)a,y=*(const double *)b;return (x>y)-(x<y);}
static void select_api(int host) {
#if defined(GMATH_CURRENTINT_REFERENCE)
  ld=host?gmath_lrint_prior:gmath_lrint;lf=host?gmath_lrintf_prior:gmath_lrintf;
  lld=host?gmath_llrint_prior:gmath_llrint;llf=host?gmath_llrintf_prior:gmath_llrintf;
#else
  ld=host?lrint:gmath_lrint;lf=host?lrintf:gmath_lrintf;
  lld=host?llrint:gmath_llrint;llf=host?llrintf:gmath_llrintf;
#endif
}
static uint64_t call(unsigned api,unsigned i) {
  switch(api) {
    case 0:return (uint64_t)ld(dx[i]);
    case 1:return (uint64_t)lld(dx[i]);
    case 2:return (uint64_t)lf(fx[i]);
    default:return (uint64_t)llf(fx[i]);
  }
}
static void setup(int mode,int seeded) {
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) ||
      (seeded && feraiseexcept(FE_UNDERFLOW|FE_INEXACT))) {exit(2);}
  errno=seeded?733:0;
}
/* Untimed host nearby rounding supplies a range classifier, not an
 * independent accuracy proof. Corpus oracles provide that proof separately. */
static int classification(unsigned api,unsigned i,int mode) {
  uint64_t raw=api<2?bits64(dx[i]):bits32(fx[i]);
  unsigned p=api<2?52u:23u;
  if (((raw>>p)&(api<2?2047u:255u))==(api<2?2047u:255u)) {return 1;}
  if (fesetround(mode)) {exit(2);}
  double x=api<2?dx[i]:(double)fx[i];
  double (*volatile rounder)(double)=nearbyint;
  double rounded=rounder(x);
  double boundary=((api==0||api==2)&&LONG_MAX==INT32_MAX)?0x1p31:0x1p63;
  if (rounded < -boundary || rounded >= boundary) {return 1;}
  return x!=rounded?2:0;
}
static uint64_t measure(unsigned api,int host,int mode,int seeded,int added,uint64_t expected_hash) {
  select_api(host);setup(mode,seeded);
  int incoming=fetestexcept(FE_ALL_EXCEPT);
  uint64_t hash=0,start=tick();
  for(unsigned i=0;i<N;i++) {hash+=call(api,i);}
  uint64_t elapsed=tick()-start;sink^=hash;
  if (hash!=expected_hash) {fputs("currentint timed checksum mismatch\n",stderr);exit(2);}
  int expected=incoming|added;
  int compare_state=!host || !(added&FE_INVALID);
#if defined(GMATH_CURRENTINT_REFERENCE)
  compare_state=1;
#endif
  if (fegetround()!=mode || (compare_state &&
      (errno!=(seeded?733:0) || fetestexcept(FE_ALL_EXCEPT)!=expected))) {fputs("currentint timed comparison state mismatch\n",stderr);exit(2);}
  return elapsed;
}
int main(int argc,char ** argv) {
  int validate=argc==2&&!strcmp(argv[1],"--validate-only");
  if (argc!=1&&!validate) {return 2;}
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const char * mode_names[]={"nearest","down","up","zero"};
  const char * apis[]={"lrint","llrint","lrintf","llrintf"};
  const char * ranges[]={"normal","half-ties","subnormal","large-integral","zero","infinity","qNaN","sNaN","wide-integral","finite-overflow","boundary32"};
  uint64_t state=UINT64_C(0x6c72696e74706169);
  printf("8 paired warmups;%u alternating pairs%u; integer timestamps; median ns/call and paired p10/median/p90; call/loop/checksum/clock and first-exception amortization included\n",(unsigned)PAIRS,(unsigned)N);
  printf("currentint.identity long%zu compiler %s built %s %s\n",sizeof(long)*CHAR_BIT,__VERSION__,__DATE__,__TIME__);
#if defined(GMATH_CURRENTINT_REFERENCE)
  puts("currentint.comparison actual-prior");
  fputs(GMATH_CURRENTINT_BASELINE_IDENTITY,stdout);
#else
  puts("currentint.comparison host-libm");
#endif
  for(unsigned api=0;api<4;api++) {
    unsigned p=api<2?52u:23u,width=api<2?64u:32u;
    uint64_t sign=UINT64_C(1)<<(width-1),inf=(api<2?UINT64_C(2047):UINT64_C(255))<<p;
    for(unsigned range=0;range<11;range++) {
      if (fesetround(FE_TONEAREST)) {return 2;}
      for(unsigned i=0;i<N;i++) {
        uint64_t z=rng(&state),word;
        if (range<2 || range==3) {
          double v=range==0?(double)((int)(z%200001)-100000)/16.0:
              range==1?(double)((int)(z%2001)-1000)+0.5:(double)((int)(z%2000000001)-1000000000);
          word=api<2?bits64(v):bits32((float)v);
        }
        else if (range==2) {word=(z&((UINT64_C(1)<<p)-1))|1u|(z&sign);}
        else if (range==4) {word=z&sign;}
        else if (range==5) {word=inf|(z&sign);}
        else if (range<8) {word=inf|(z&sign)|(range==6?UINT64_C(1)<<(p-1):0)|(z&((UINT64_C(1)<<(p-1))-1))|1u;}
        else if (range==8) {
          unsigned bias=api<2?1023u:127u;
          word=((uint64_t)(bias+52u+(unsigned)(z%11))<<p)|(z&((UINT64_C(1)<<p)-1))|(z&sign);
          if (i%128==0) {word=((uint64_t)(bias+63)<<p)|sign;}
        }
        else if (range==9) {
          unsigned bias=api<2?1023u:127u;
          word=((uint64_t)(bias+64)<<p)|(z&((UINT64_C(1)<<p)-1))|(z&sign);
          if (i%3==0) {word=(uint64_t)(bias+63)<<p;}
        }
        else if (api<2) {
          double x=0x1p31+(double)((int)(z%11)-5)/4.0;
          word=bits64(x)|(z&sign);
        }
        else {word=(UINT64_C(0x4f000000)+(z%7)-3)|(z&sign);}
        if (api<2) {memcpy(&dx[i],&word,8);}
        else {uint32_t raw=(uint32_t)word;memcpy(&fx[i],&raw,4);}
      }
      for(unsigned mode=0;mode<4;mode++) {
        for(int seeded=0;seeded<2;seeded++) {
          int batch_flags=0;uint64_t own_checksum=0,host_checksum=0;
          for(unsigned i=0;i<N;i++) {
            int flag=classification(api,i,modes[mode]);batch_flags|=flag==1?FE_INVALID:flag==2?FE_INEXACT:0;select_api(0);setup(modes[mode],seeded);int incoming=fetestexcept(FE_ALL_EXCEPT);
            uint64_t own=call(api,i);int want=incoming|(flag==1?FE_INVALID:flag==2?FE_INEXACT:0);
            if (errno!=(seeded?733:0)||fegetround()!=modes[mode]||fetestexcept(FE_ALL_EXCEPT)!=want) {fputs("currentint own per-input state mismatch\n",stderr);return 2;}
            if (flag==1) {
              uint64_t minimum=(api==0||api==2)?(uint64_t)LONG_MIN:(uint64_t)LLONG_MIN;
              if (own!=minimum) {return 2;}
            }
            select_api(1);setup(modes[mode],seeded);incoming=fetestexcept(FE_ALL_EXCEPT);uint64_t host=call(api,i);
            own_checksum+=own;host_checksum+=host;
            int compare_other=flag!=1;
#if defined(GMATH_CURRENTINT_REFERENCE)
            compare_other=1;
#endif
            if (compare_other && (host!=own || errno!=(seeded?733:0)||fegetround()!=modes[mode]||fetestexcept(FE_ALL_EXCEPT)!=(incoming|(flag==1?FE_INVALID:flag==2?FE_INEXACT:0)))) {fputs("currentint comparison per-input value/state mismatch\n",stderr);return 2;}
          }
          if (validate) {continue;}
          for(unsigned warm=0;warm<8;warm++) {
            (void)measure(api,warm&1,modes[mode],seeded,batch_flags,(warm&1)?host_checksum:own_checksum);
            (void)measure(api,!(warm&1),modes[mode],seeded,batch_flags,!(warm&1)?host_checksum:own_checksum);
          }
          uint64_t own[PAIRS],host[PAIRS];double ratios[PAIRS];
          for(unsigned pair=0;pair<PAIRS;pair++) {
            if (pair&1) {host[pair]=measure(api,1,modes[mode],seeded,batch_flags,host_checksum);own[pair]=measure(api,0,modes[mode],seeded,batch_flags,own_checksum);}
            else {own[pair]=measure(api,0,modes[mode],seeded,batch_flags,own_checksum);host[pair]=measure(api,1,modes[mode],seeded,batch_flags,host_checksum);}
            if (!host[pair]||fesetround(FE_TONEAREST)) {return 2;}
            ratios[pair]=(double)own[pair]/(double)host[pair];
          }
          qsort(own,PAIRS,sizeof *own,cmpu);qsort(host,PAIRS,sizeof *host,cmpu);qsort(ratios,PAIRS,sizeof *ratios,cmpd);
          printf("currentint %s %s %s %s own %.3f host %.3f ratio %.3f %.3f %.3f\n",apis[api],ranges[range],mode_names[mode],seeded?"UF/IX":"clean",(double)own[PAIRS/2]/N,(double)host[PAIRS/2]/N,ratios[PAIRS/10],ratios[PAIRS/2],ratios[9*PAIRS/10]);
        }
      }
    }
  }
  if (validate) {puts("currentint352 cases per-input guards pass");}
  return sink==UINT64_C(0xdeadbeef)?1:0;
}
