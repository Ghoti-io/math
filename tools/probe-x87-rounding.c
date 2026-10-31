/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Bare C no-SSE client: no platform fenv calls or host libm references.
 */
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#if !defined(__i386__) || defined(__SSE__)
#error "This probe requires an i386 target without SSE"
#endif

static uint16_t control(void) {
  uint16_t word;
  __asm__ volatile("fnstcw %0" : "=m"(word) : : "memory");
  return word;
}
static unsigned status(void) {
  uint16_t word;
  __asm__ volatile("fnstsw %0" : "=am"(word) : : "memory");
  return word & 0x3du; /* Standard C flags, excluding denormal-operand status. */
}
static void setup(uint16_t word,unsigned seed) {
  __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(word) : "memory");
  if(seed==1) {
    volatile double tiny=0x1p-1022;
    volatile double ignored=tiny*tiny;
    (void)ignored;
  } else if(seed==2) {
    volatile double zero=0.0;
    volatile double ignored=zero/zero;
    (void)ignored;
  }
  errno=733;
}
struct example {double x;int64_t nearest,down,up,zero;unsigned fractional,double_only;};
static const struct example cases[]={
  {0.0,0,0,0,0,0,0},{-0.0,0,0,0,0,0,0},{1.0,1,1,1,1,0,0},{-1.0,-1,-1,-1,-1,0,0},
  {0.5,0,0,1,0,1,0},{-0.5,0,-1,0,0,1,0},{0.75,1,0,1,0,1,0},{-0.75,-1,-1,0,0,1,0},
  {1.5,2,1,2,1,1,0},{-1.5,-2,-2,-1,-1,1,0},{2.5,2,2,3,2,1,0},{-2.5,-2,-3,-2,-2,1,0},
  {1.25,1,1,2,1,1,0},{-1.25,-1,-2,-1,-1,1,0},
  {8388607.5,8388608,8388607,8388608,8388607,1,0},
  {-8388607.5,-8388608,-8388608,-8388607,-8388607,1,0},
  {8388609.0,8388609,8388609,8388609,8388609,0,0},
  {-8388609.0,-8388609,-8388609,-8388609,-8388609,0,0},
  {1073741760.0,1073741760,1073741760,1073741760,1073741760,0,0},
  {-1073741760.0,-1073741760,-1073741760,-1073741760,-1073741760,0,0},
  {1073741824.0,1073741824,1073741824,1073741824,1073741824,0,0},
  {-1073741824.0,-1073741824,-1073741824,-1073741824,-1073741824,0,0},
  {1073741824.5,1073741824,1073741824,1073741825,1073741824,1,1},
  {-1073741824.5,-1073741824,-1073741825,-1073741824,-1073741824,1,1}
};
int main(void) {
  uint16_t saved=control();uint64_t calls=0;
  const unsigned precisions[]={0,2,3}; /* 24, 53 and 64 significand bits. */
  for(unsigned pc=0;pc<3;++pc) for(unsigned mode=0;mode<4;++mode)
    for(unsigned seed=0;seed<3;++seed) for(unsigned i=0;i<sizeof cases/sizeof *cases;++i) {
      int64_t bymode[]={cases[i].nearest,cases[i].down,cases[i].up,cases[i].zero};
      float f=(float)cases[i].x;uint64_t input;uint32_t inputf;
      memcpy(&input,&cases[i].x,8);memcpy(&inputf,&f,4);
      uint16_t cw=(uint16_t)((saved&~0x0f00u)|0x003fu|(precisions[pc]<<8)|(mode<<10));
      for(unsigned api=0;api<8;++api) {
        /* Wider double inputs are exercised at 53/64-bit precision. The
         * 24-bit profile uses inputs exactly representable at that precision,
         * keeping caller argument/return conversions out of the flag check. */
        if(cases[i].double_only&&((api&1u)||pc==0)) continue;
        int64_t wanted=api==2||api==3?cases[i].nearest:bymode[mode];
        double dtarget=(double)wanted;float ftarget=(float)wanted;
        uint64_t expected;uint32_t expectedf;
        memcpy(&expected,&dtarget,8);memcpy(&expectedf,&ftarget,4);
        if(!wanted) {expected=input&UINT64_C(0x8000000000000000);expectedf=inputf&UINT32_C(0x80000000);}
        setup(cw,seed);unsigned incoming=status();
        if(incoming!=(seed==1?0x30u:seed==2?1u:0u)) {fputs("x87 seed fixture differs\n",stderr);return 2;}
        uint64_t got=0;int64_t integer=0;
        switch(api) {
          case 0:{double r=gmath_nearbyint(cases[i].x);memcpy(&got,&r,8);break;}
          case 1:{float r=gmath_nearbyintf(f);uint32_t w;memcpy(&w,&r,4);got=w;break;}
          case 2:{double r=gmath_rint(cases[i].x);memcpy(&got,&r,8);break;}
          case 3:{float r=gmath_rintf(f);uint32_t w;memcpy(&w,&r,4);got=w;break;}
          case 4:integer=gmath_lrint(cases[i].x);break;
          case 5:integer=gmath_lrintf(f);break;
          case 6:integer=gmath_llrint(cases[i].x);break;
          default:integer=gmath_llrintf(f);break;
        }
        unsigned flags=status();int error=errno;uint16_t after=control();
        unsigned wantflags=incoming|((api>=4&&cases[i].fractional)?0x20u:0u);
        int wrong=api<4?got!=((api&1u)?expectedf:expected):integer!=wanted;
        if(wrong||flags!=wantflags||after!=cw||error!=733) {
          fprintf(stderr,"x87 api%u case%u mode%u precision%u seed%u got%016" PRIx64
              " integer%" PRId64 " wanted%" PRId64 " flags%x/%x control%x/%x errno%d\n",
              api,i,mode,precisions[pc],seed,got,integer,wanted,flags,wantflags,after,cw,error);
          __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(saved) : "memory");
          return 1;
        }
        ++calls;
      }
    }
  __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(saved) : "memory");
  printf("x87 nearby/rint/currentint 4 modes 3 precisions 3 incoming states %" PRIu64 " calls pass\n",calls);
  return 0;
}
