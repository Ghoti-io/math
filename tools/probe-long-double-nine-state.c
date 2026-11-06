/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Bounded-stack and targeted DAZ/FTZ client. No arithmetic implementation. */
#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#define GMATH_LONG_DOUBLE_NINE_RAW_ONLY
#include "../src/elementary/long_double_nine.c"
#include "../tests/long_double_nine_abi.h"
#include "../tests/fp_controls.h"
#include <errno.h>
#include <fenv.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
#define LD9_USABLE_STACK (2u*1024u*1024u)
static volatile uint64_t checksum;
static unsigned state_flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw state_native(unsigned op,ld_raw a,ld_raw b,ld_raw c,uint64_t *integer,int *q) {
  long double x,y,z,out;ld_write((unsigned char *)&x,a);ld_write((unsigned char *)&y,b);ld_write((unsigned char *)&z,c);(void)q;
#if defined(LD9_BYTE_CALLER)
  ld9_native80_bytes((int)op,&x,&y,&z,&out,q,integer);
#else
  ld_raw zero={0,0};
  switch(op) {
    case 0:*integer=(uint64_t)(int64_t)gmath_lroundl(x);return zero;
    case 1:*integer=(uint64_t)(int64_t)gmath_llroundl(x);return zero;
    case 2:*integer=(uint64_t)(int64_t)gmath_lrintl(x);return zero;
    case 3:*integer=(uint64_t)(int64_t)gmath_llrintl(x);return zero;
#if GMATH_HAVE_LONG_DOUBLE_REMAINDER
    case 4:out=gmath_fmodl(x,y);break;
    case 5:out=gmath_remainderl(x,y);break;
    case 6:out=gmath_remquol(x,y,q);break;
    case 9:out=gmath_remquol(x,y,NULL);break;
#endif
    case 7:out=gmath_fdiml(x,y);break;
    case 8:out=gmath_fmal(x,y,z);break;
    default:abort();
  }
#endif
  return ld_read((const unsigned char *)&out);
}
static int population(unsigned fmt,int native) {
  ld_value v={{0},0,LD_FINITE,0};int min=fmt==64||fmt==106?-1074:fmt==80?-16445:-16494;
  ld_insert(&v,1,min);ld_raw tiny=ld_pack(fmt,&v);ld_shift(&v,1);ld_raw twice=ld_pack(fmt,&v);
  memset(v.w,0,sizeof v.w);ld_insert(&v,1,0);ld_raw one=ld_pack(fmt,&v);ld_shift(&v,-1);ld_raw half=ld_pack(fmt,&v),zero={0,0};
  for(unsigned op=0;op<=10;++op) {
    unsigned public_op=op==10?8:op;ld_raw a=op==7?twice:tiny,b=op<=6||op==9?twice:op==7?tiny:op==10?half:one;
    ld_raw want=op<4||op==10?zero:tiny;
    unsigned required=op==2||op==3?4:op==10?12:0;
    if(feclearexcept(FE_ALL_EXCEPT))return 1;
    unsigned incoming=state_flags();if(incoming)return 2;
    uint64_t control=gmath_test_controls(),integer=0;int q=0;errno=173;
    ld_raw got={0,0};
    if(native)got=state_native(public_op,a,b,zero,&integer,&q);
    else if(op<4)integer=(uint64_t)ldn_integer(fmt,a,op>=2,0,64);
    else got=ldn_run(fmt,op==9?LDN_REMQUO:(int)public_op-4,a,b,zero,0,op==6?&q:NULL);
    if(got.hi!=want.hi||got.lo!=want.lo||integer||q||state_flags()!=required||errno!=173||control!=gmath_test_controls()) {
      fprintf(stderr,"nine state: fmt%u native%d op%u rejected\n",fmt,native,op);return 3;
    }
    checksum^=got.hi^got.lo;
  }
  if(fmt==106) {
    /* (2^1023+2^-1074)/2^-1074 = 2^2097+1 exactly. This enters
     * all 2098 quotient positions and the 67-word stream; q mod128 is one. */
    for(unsigned negative=0;negative<2;++negative)
      for(unsigned index=0;index<4;++index) {
        const unsigned ops[4]={4,5,6,9};unsigned op=ops[index];
        ld_raw a={UINT64_C(0x7fe0000000000000)|((uint64_t)negative<<63),
                  1|((uint64_t)negative<<63)},divisor={1,0},got;
        if(feclearexcept(FE_ALL_EXCEPT))return 4;
        uint64_t control=gmath_test_controls(),integer=0;int q=0;errno=173;
        if(native)got=state_native(op,a,divisor,zero,&integer,&q);
        else got=ldn_run(106,op==9?LDN_REMQUO:(int)op-4,a,divisor,zero,0,op==6?&q:NULL);
        int want_q=op==6?(negative?-1:1):0;
        if(got.hi!=((uint64_t)negative<<63) || got.lo || integer || q!=want_q ||
           state_flags() || errno!=173 || control!=gmath_test_controls()) {
          fprintf(stderr,"nine state: maximum-gap DD native%d op%u negative%u rejected\n",native,op,negative);return 5;
        }
        checksum^=got.hi^(uint64_t)(unsigned)q;
      }
  }
  return 0;
}
static void *worker(void *unused) {
  (void)unused;fenv_t saved;if(fegetenv(&saved)||fesetround(FE_TONEAREST))return (void *)1;
  int status=0;
#if defined(__SSE__) && (defined(__i386__)||defined(__x86_64__))
  _Alignas(16) unsigned char fx[512];uint32_t mask=0,original=0;
  __asm__ volatile("fxsave %0":"=m"(fx));memcpy(&mask,fx+28,4);if(!mask)mask=0xffbf;
  __asm__ volatile("stmxcsr %0":"=m"(original));
  const unsigned profiles[4]={0,0x40,0x8000,0x8040};
  for(unsigned p=0;p<4&&!status;++p) {
    if(profiles[p]&~mask){printf("nine state: unsupported MXCSR profile %x skipped\n",profiles[p]);continue;}
    uint32_t control=(original&~0x8040u)|profiles[p];__asm__ volatile("ldmxcsr %0"::"m"(control));
#else
  for(unsigned p=0;p<1&&!status;++p) {
    (void)p;
#endif
    const unsigned formats[4]={64,80,128,106};
    for(unsigned f=0;f<4&&!status;++f)status=population(formats[f],0);
    if(!status)status=population(LD_NATIVE,1);
  }
  /* Exercise the fixed, deeply nested DD decode/population path as well. */
  ld_raw a={UINT64_C(0x3ff0000000000000),1},b={UINT64_C(0x3ff0000000000000),UINT64_C(0x8000000000000001)},c={UINT64_C(0xbff0000000000000),0};
  ld_raw r=ldn_run(106,LDN_FMA,a,b,c,0,NULL);checksum^=r.hi^r.lo;
  if(fesetenv(&saved))status=4;
  return (void *)(uintptr_t)status;
}
int main(void) {
  (void)lds_run; (void)ldn_mode;
  long page=sysconf(_SC_PAGESIZE);if(page<=0)return 2;
  size_t allocation=LD9_USABLE_STACK+2*(size_t)page;
  unsigned char *memory=mmap(NULL,allocation,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  if(memory==MAP_FAILED || mprotect(memory+page,LD9_USABLE_STACK,PROT_READ|PROT_WRITE))return 2;
  pthread_attr_t attr;pthread_t thread;void *result=NULL;
  if(pthread_attr_init(&attr)||pthread_attr_setguardsize(&attr,0)||pthread_attr_setstack(&attr,memory+page,LD9_USABLE_STACK)||pthread_create(&thread,&attr,worker,NULL))return 2;
  if(pthread_join(thread,&result))return 2;
  pthread_attr_destroy(&attr);munmap(memory,allocation);
  if(result)return 1;
  printf("nine state/stack: %u usable bytes with two guard pages; supported DAZ/FTZ profiles preserved\n",LD9_USABLE_STACK);return 0;
}
