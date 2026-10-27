/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Same-input alternating indirect calls; no application speedup claim.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/elementary.h>
#include <fenv.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
static float inputs[N];
static volatile uint32_t sink;
static uint32_t state=0x6174616eu;
static uint32_t random_word(void) {state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static float value(uint32_t bits) {float x;memcpy(&x,&bits,4);return x;}
static int seeded;
static double measure(float (*volatile fn)(float)) {
  if (feclearexcept(FE_ALL_EXCEPT)||(seeded&&feraiseexcept(FE_UNDERFLOW|FE_INEXACT))) exit(2);
  uint32_t sum=0;struct timespec start,end;
  if (clock_gettime(CLOCK_MONOTONIC,&start)) {perror("clock_gettime");exit(2);}
  if (fetestexcept(FE_ALL_EXCEPT)!=(seeded?(FE_UNDERFLOW|FE_INEXACT):0)) exit(2);
  for (int i=0;i<N;++i) {float y=fn(inputs[i]);uint32_t raw;memcpy(&raw,&y,4);sum+=raw;}
  if (clock_gettime(CLOCK_MONOTONIC,&end)) {perror("clock_gettime");exit(2);}
  double elapsed=((double)(end.tv_sec-start.tv_sec)*1e9+(double)(end.tv_nsec-start.tv_nsec))/N;
  sink=sum;return elapsed;
}
static int compare(const void * a,const void * b) {double x=*(const double *)a,y=*(const double *)b;return (x>y)-(x<y);}
int main(void) {
  if (fesetenv(FE_DFL_ENV)||fesetround(FE_TONEAREST)) return 2;
  const char * names[]={"common signed","table [1/8,1]","direct [0,1/8]","tiny normal","subnormal","wide finite"};
  puts("atanf: 401 alternating same-input pairs, indirect calls; gmath/libm ratios include loop/checksum overhead");
  for (seeded=0;seeded<2;++seeded) for (int range=0;range<6;++range) {
    for (int i=0;i<N;++i) {
      uint32_t raw=random_word();float u=(float)(raw&0x7fffffu)*0x1p-23f;
      switch (range) {
      case 0:inputs[i]=(u-0.5f)*20.0f;break;
      case 1:inputs[i]=0.125f+0.875f*u;break;
      case 2:inputs[i]=0x1p-20f+(0.125f-0x1p-20f)*u;break;
      case 3:inputs[i]=value((raw&0x807fffffu)|((1u+raw%96u)<<23));break;
      case 4:inputs[i]=value((raw&0x807fffffu)|1u);break;
      default:inputs[i]=value((raw&0x807fffffu)|((raw%255u)<<23));break;
      }
    }
    for (int r=0;r<10;++r) {(void)measure(gmath_atanf);(void)measure(atanf);}
    double ratios[401];
    for (int r=0;r<401;++r) {
      double a,b;if (r&1) {b=measure(atanf);a=measure(gmath_atanf);}else {a=measure(gmath_atanf);b=measure(atanf);}
      ratios[r]=a/b;
    }
    qsort(ratios,401,sizeof *ratios,compare);printf("%-20s %s batch-entry flags median %.3fx\n",names[range],seeded?"UF/IX":"clean",ratios[200]);
  }
  return 0;
}
