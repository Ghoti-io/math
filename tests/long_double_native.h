/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Native ABI corpus client, independent of production integer adapters. */
#ifndef GMATH_LONG_DOUBLE_NATIVE_H
#define GMATH_LONG_DOUBLE_NATIVE_H
#include <ghoti.io/math/basic.h>
#include <float.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <inttypes.h>
#include <fenv.h>
#include <errno.h>
#include "corpus_hash.h"
#if LDBL_MANT_DIG == 53
#define LDN_FORMAT 64
#elif LDBL_MANT_DIG == 64
#define LDN_FORMAT 80
#elif LDBL_MANT_DIG == 113
#define LDN_FORMAT 128
#elif LDBL_MANT_DIG == 106
#define LDN_FORMAT 106
#else
#error Unsupported native long double
#endif
typedef struct { uint64_t hi,lo; } ldn_raw;
static void ldn_store(void *ptr,ldn_raw r) {
  unsigned char *p=(unsigned char *)ptr;memset(p,0,sizeof(long double));
#if LDN_FORMAT == 80
  uint16_t se=(uint16_t)r.hi;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(p,&se,2);memcpy(p+sizeof(long double)-8,&r.lo,8);
#else
  memcpy(p,&r.lo,8);memcpy(p+8,&se,2);
#endif
#elif LDN_FORMAT == 128 && (!defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__)
  memcpy(p,&r.lo,8);memcpy(p+8,&r.hi,8);
#else
  memcpy(p,&r.hi,8);
#if LDN_FORMAT != 64
  memcpy(p+8,&r.lo,8);
#endif
#endif
}
static ldn_raw ldn_load(const void *ptr) {
  const unsigned char *p=(const unsigned char *)ptr;ldn_raw r={0,0};
#if LDN_FORMAT == 80
  uint16_t se;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(&se,p,2);memcpy(&r.lo,p+sizeof(long double)-8,8);
#else
  memcpy(&r.lo,p,8);memcpy(&se,p+8,2);
#endif
  r.hi=se;
#elif LDN_FORMAT == 128 && (!defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__)
  memcpy(&r.lo,p,8);memcpy(&r.hi,p+8,8);
#else
  memcpy(&r.hi,p,8);
#if LDN_FORMAT != 64
  memcpy(&r.lo,p+8,8);
#endif
#endif
  return r;
}
static ldn_raw ldn_call(int op,ldn_raw a,ldn_raw b,ldn_raw *whole,int *e) {
  long double x,y,z,w;ldn_store(&x,a);ldn_store(&y,b);
  switch(op) {
#define LDN_UNARY(n,k) case k:z=gmath_##n(x);break
    LDN_UNARY(fabsl,0);LDN_UNARY(floorl,5);LDN_UNARY(ceill,6);LDN_UNARY(truncl,7);
    LDN_UNARY(roundl,8);LDN_UNARY(rintl,9);LDN_UNARY(nearbyintl,10);LDN_UNARY(logbl,14);
    case 1:z=gmath_copysignl(x,y);break;
    case 2:z=gmath_nanl((const char *)(uintptr_t)1);break;
    case 3:z=gmath_fminl(x,y);break;
    case 4:z=gmath_fmaxl(x,y);break;
    case 11:z=gmath_modfl(x,&w);*whole=ldn_load(&w);break;
#if GMATH_HAVE_FREXPL
    case 12:z=gmath_frexpl(x,e);break;
#endif
    case 13:*e=gmath_ilogbl(x);return a;
    default:return a;
  }
  return ldn_load(&z);
}
static int ldn_corpus(const char *directory,int print) {
  char path[4096];snprintf(path,sizeof path,"%s/long-double-foundation.corpus",directory);
  FILE *file=fopen(path,"r");if (!file)return 1;
  fenv_t saved;int saved_errno=errno;if(fegetenv(&saved)){fclose(file);return 1;}
  const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  unsigned fmt,op,mode,pc,inc,flags;ldn_raw a,b,r,w;int e;unsigned long count=0;uint64_t hash=UINT64_C(14695981039346656037);
  int status=0,parsed=0;
  while ((parsed=fscanf(file,"%u %u %" SCNx64 " %" SCNx64 " %" SCNx64 " %" SCNx64 " %u %u %u %" SCNx64 " %" SCNx64 " %" SCNx64 " %" SCNx64 " %d %u",&fmt,&op,&a.hi,&a.lo,&b.hi,&b.lo,&mode,&pc,&inc,&r.hi,&r.lo,&w.hi,&w.lo,&e,&flags))==15) {
    if ((fmt!=64 && fmt!=80 && fmt!=128 && fmt!=106) || op>=15 || mode>=4 || (pc!=0 && pc!=2 && pc!=3) || inc>31 || flags>31 || (fmt==106 && op==12)) {status=1;break;}
    if(fmt!=LDN_FORMAT)continue;
    if(fesetround(modes[mode]) || feclearexcept(FE_ALL_EXCEPT)){status=1;break;}
    if(inc)feraiseexcept(((inc&1)?FE_INVALID:0)|((inc&2)?FE_DIVBYZERO:0)|((inc&4)?FE_INEXACT:0)|((inc&8)?FE_UNDERFLOW:0)|((inc&16)?FE_OVERFLOW:0));
    ldn_raw whole={0,0};int exponent=0;errno=173;
    ldn_raw got=ldn_call((int)op,a,b,&whole,&exponent);int err=errno;
    int f=fetestexcept(FE_ALL_EXCEPT);
    unsigned actual=((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
    if ((op!=13 && (got.hi!=r.hi || got.lo!=r.lo)) || (op==11 && (whole.hi!=w.hi || whole.lo!=w.lo)) || exponent!=e || actual!=flags || err!=173) {fprintf(stderr,"long-double native corpus: row %lu op%u rejected\n",count,op);status=1;break;}
    if(op==13)got.hi=got.lo=0;
    hash=gmath_fnv_u64(hash,got.hi);hash=gmath_fnv_u64(hash,got.lo);
    hash=gmath_fnv_u64(hash,whole.hi);hash=gmath_fnv_u64(hash,whole.lo);
    hash=gmath_fnv_u64(hash,(uint64_t)(int64_t)exponent);hash=gmath_fnv_u64(hash,actual);++count;
  }
  if(parsed!=EOF || ferror(file) || !count)status=1;
  fclose(file);
  snprintf(path,sizeof path,"%s/long-double-foundation.hash",directory);
  file=fopen(path,"r");
  if(!file)status=1;
  else {
    unsigned format;uint64_t want;unsigned long population;int found=0;
    while(fscanf(file,"format %u %" SCNx64 " %lu\n",&format,&want,&population)==3)
      if(format==LDN_FORMAT) { ++found;if(want!=hash || population!=count)status=1; }
    if(found!=1 || ferror(file))status=1;
    fclose(file);
  }
  if(fesetenv(&saved))status=1;
  errno=saved_errno;
  if(print)printf("math.long_double.format%d.hash %016" PRIx64 "\nmath.long_double.format%d.count %lu\n",LDN_FORMAT,hash,LDN_FORMAT,count);
  return status;
}
#endif
