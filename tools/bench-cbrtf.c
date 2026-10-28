/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired Float cube-root scalar timings with untimed numerical/state guards.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
#define PAIRS 401
static uint32_t raw[N];
static float inputs[N];
static volatile uint64_t sink;
static float (*volatile call)(float);
static uint32_t bits(float f) {uint32_t u;memcpy(&u,&f,4);return u;}
static uint64_t tick(void) {struct timespec t;if (clock_gettime(CLOCK_MONOTONIC,&t)) exit(2);return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;}
static uint32_t random_word(uint32_t *s) {*s^=*s<<13;*s^=*s>>17;*s^=*s<<5;return *s;}
static int required(uint32_t u) {
  uint32_t a=u&0x7fffffffu;
  if (a>0x7f800000u) return a&0x00400000u?0:FE_INVALID;
  if (!a||a==0x7f800000u) return 0;
  int e;uint32_t m;
  if (a>=0x00800000u) {e=(int)(a>>23)-127;m=a&0x007fffffu;return !m&&e%3==0?0:FE_INEXACT;}
  if (a&(a-1u)) return FE_INEXACT;
  e=-149;while (a>1) {a>>=1;++e;}return e%3==0?0:FE_INEXACT;
}
static uint64_t measure(int host,int seeded,int need) {
  call=host?cbrtf:gmath_cbrtf;
  if (fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(seeded?(FE_UNDERFLOW|FE_INEXACT):0)) exit(2);
  int incoming=fetestexcept(FE_ALL_EXCEPT),error_seed=seeded?733:0;errno=error_seed;
  uint64_t sum=0,start=tick();
  for (int i=0;i<N;i++) {float y=call(inputs[i]);sum+=bits(y);}
  uint64_t end=tick();int flags=fetestexcept(FE_ALL_EXCEPT),error=errno,mode=fegetround();sink+=sum;
  if (mode!=FE_TONEAREST||(flags&incoming)!=incoming||(!host&&(flags!=(incoming|need)||error!=error_seed))) {
    fputs("cbrtf timing state guard failed\n",stderr);exit(2);
  }
  return end-start;
}
static int cmpu(const void *a,const void *b) {uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;return (x>y)-(x<y);}
static int cmpd(const void *a,const void *b) {double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
int main(void) {
  static const char *names[]={"normal","binary-powers","other-exact-cubes","subnormal","wide","zero","infinity","quiet-NaN","signaling-NaN"};
  printf("compiler %s; C%ld; nearest; integer timestamps\n",__VERSION__,(long)__STDC_VERSION__);
  puts("8 paired warmups;401 alternating pairs of4096 same inputs; clean/preseeded UF/IX and errno; median ns/call and paired ratio p10/median/p90; call/loop/checksum/timestamp and first-exception amortization included; host new flags, exceptional errno and NaN payloads may differ");
  uint32_t state=0x63756265u;
  for (unsigned range=0;range<sizeof names/sizeof *names;range++) {
    int need=0;
    for (int i=0;i<N;i++) {
      uint32_t word=random_word(&state),sign=word&0x80000000u;
      if (range==0) word=0x3f000000u|(word&0x00ffffffu);
      else if (range==1) {int e=3*((i%89)-49);word=e>=-126?(uint32_t)(e+127)<<23:1u<<(e+149);}
      else if (range==2) {float r=(float)(3+2*(i%6));word=bits(r*r*r);}
      else if (range==3) word=(word&0x007fffffu)|1u;
      else if (range==4) word=word%0x7f800000u;
      else if (range==5) word=0;
      else if (range==6) word=0x7f800000u;
      else if (range==7) word=0x7fc00000u|(word&0x003fffffu);
      else word=0x7f800001u|(word&0x003fffffu);
      raw[i]=word|sign;memcpy(&inputs[i],&raw[i],4);need|=required(raw[i]);
      float own=gmath_cbrtf(inputs[i]),host=cbrtf(inputs[i]);uint32_t a=raw[i]&0x7fffffffu;
      if (a>0x7f800000u) {if (bits(own)!=0x7fc00000u||!isnan(host)) return 2;}
      else if (!a||a==0x7f800000u) {if (bits(own)!=raw[i]||bits(host)!=raw[i]) return 2;}
      else {
        /* Host Double cube root is a coarse independent timing guard only. */
        double reference=cbrt((double)inputs[i]);int e=0;(void)frexp(fabs(reference),&e);double unit=ldexp(1.0,e-24);
        if (fabs((double)own-reference)>2*unit||fabs((double)host-reference)>2*unit) return 2;
      }
    }
    for (int seeded=0;seeded<2;seeded++) {
      for (int warm=0;warm<8;warm++) {(void)measure(warm&1,seeded,need);(void)measure(!(warm&1),seeded,need);}
      uint64_t own[PAIRS],host[PAIRS];double ratio[PAIRS];
      for (int pair=0;pair<PAIRS;pair++) {
        if (pair&1) {host[pair]=measure(1,seeded,need);own[pair]=measure(0,seeded,need);}
        else {own[pair]=measure(0,seeded,need);host[pair]=measure(1,seeded,need);}
        if (!host[pair]) return 2;
        ratio[pair]=(double)own[pair]/(double)host[pair];
      }
      qsort(own,PAIRS,sizeof *own,cmpu);qsort(host,PAIRS,sizeof *host,cmpu);qsort(ratio,PAIRS,sizeof *ratio,cmpd);
      printf("cbrtf %s %s gmath %.3f host %.3f ratio %.3f %.3f %.3f\n",names[range],seeded?"UF/IX":"clean",(double)own[PAIRS/2]/N,(double)host[PAIRS/2]/N,ratio[PAIRS/10],ratio[PAIRS/2],ratio[9*PAIRS/10]);
    }
  }
  return sink==UINT64_C(0xdeadbeef)?1:0;
}
