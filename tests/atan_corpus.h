/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Bounded raw corpus checks and independent nearest closed-error cells.
 */
#ifndef GMATH_TEST_ATAN_CORPUS_H
#define GMATH_TEST_ATAN_CORPUS_H
#include "atan_probe.h"
#include "corpus_hash.h"
#include <stdlib.h>
#include <sys/stat.h>

static double a64_value(uint64_t word) {
  double x;memcpy(&x,&word,sizeof x);return x;
}
static double a64_power(int exponent) {
  return a64_value(exponent < -1022 ? UINT64_C(1) << (exponent+1074) :
      (uint64_t)(exponent+1023) << 52);
}
static double a64_error_value(uint32_t word) {
  unsigned field=(word>>23)&255u;uint32_t mantissa=word&0x7fffffu;
  uint64_t sign=(uint64_t)(word>>31)<<63;
  if (field) {return a64_value(sign|((uint64_t)(field+896u)<<52)|((uint64_t)mantissa<<29));}
  if (!mantissa) {return a64_value(sign);}
  unsigned top=0;uint32_t t=mantissa;
  while(t>>1) {t>>=1;++top;}
  return a64_value(sign|((uint64_t)(top+874u)<<52)|
      ((uint64_t)(mantissa-(1u<<top))<<(52u-top)));
}
static int a64_accuracy(uint64_t target,uint32_t error,uint64_t got,double * maximum) {
  uint64_t a=target&UINT64_C(0x7fffffffffffffff);
  if (a>UINT64_C(0x7ff0000000000000)||!a) {return got!=target;}
  fenv_t saved;int saved_errno=errno;
  if(fegetenv(&saved)) {return 1;}
  int status=1;
  if(fesetround(FE_TONEAREST)) {goto finish;}
  {
    int e=(int)(a>>52)-1023;
    int towardzero=(!(target>>63)&&(error>>31))||((target>>63)&&!(error>>31));
    if (!(a&UINT64_C(0x000fffffffffffff))&&a>UINT64_C(0x0010000000000000)&&towardzero) {--e;}
    if(e < -1022) {e=-1022;}
    double unit=a64_power(e-52);
    double d=(a64_value(got)-a64_value(target))/unit-a64_error_value(error);
    if(d<0) {d=-d;}
    unsigned field=(error&0x7fffffffu)>>23;
    int re=(field ? (int)field-127 : -126)-24;
    double bound=d+a64_power(re);uint64_t bits;
    memcpy(&bits,&bound,sizeof bits);
    /* One outward step covers rounding in the closed-cell bound arithmetic. */
    bound=a64_value(bits+1);
    if(bound>*maximum) {*maximum=bound;}
    status=!(bound<=0.60);
  }
finish:
  if(fesetenv(&saved)) {status=1;}
  errno=saved_errno;return status;
}
static int a64_line(FILE * file,char line[256]) {
  unsigned n=0;int c;
  while((c=fgetc(file))!=EOF) {
    if(c==0||n>=254) {return -1;}
    if(c=='\n') {line[n]='\0';return 1;}
    line[n++]=(char)c;
  }
  return n ? -1 : 0;
}
static int a64_selected(uint64_t x,uint64_t index) {
  uint64_t a=x&UINT64_C(0x7fffffffffffffff);
  return index%61==0||a<UINT64_C(0x0010000000000000)||a>=UINT64_C(0x7ff0000000000000)||
      (a>=UINT64_C(0x3e0ffffffffffff8)&&a<=UINT64_C(0x3e10000000000008))||
      (a>=UINT64_C(0x434ffffffffffff8)&&a<=UINT64_C(0x4350000000000008));
}
static int a64_row_shape(uint64_t x,uint64_t target,uint32_t error,unsigned flags) {
  const uint64_t abs_mask=UINT64_C(0x7fffffffffffffff),inf=UINT64_C(0x7ff0000000000000);
  uint64_t a=x&abs_mask,t=target&abs_mask;unsigned want;
  if(a>inf) {
    want=(x&UINT64_C(0x0008000000000000))?0u:1u;
    return flags!=want||target!=UINT64_C(0x7ff8000000000000)||error;
  }
  if(!a) {return flags||target!=x||error;}
  want=a<UINT64_C(0x0010000000000000)?6u:2u;
  if(flags!=want||(error&0x7fffffffu)>0x3f000000u||!t||t>UINT64_C(0x3ff921fb54442d18)||(target>>63)!=(x>>63)) {return 1;}
  if(a<UINT64_C(0x3e10000000000000)&&target!=x) {return 1;}
  if(a>=UINT64_C(0x4350000000000000)&&target!=(UINT64_C(0x3ff921fb54442d18)|(x&~abs_mask))) {return 1;}
  return 0;
}
static int a64_decimal(const char ** cursor,uint64_t * output) {
  const char * p=*cursor;uint64_t value=0;
  if(*p<'0'||*p>'9'||(*p=='0'&&p[1]>='0'&&p[1]<='9')) {return 1;}
  while(*p>='0'&&*p<='9') {
    unsigned digit=(unsigned)(*p-'0');
    if(value>(UINT64_MAX-digit)/10) {return 1;}
    value=value*10+digit;++p;
  }
  *cursor=p;*output=value;return 0;
}
static int a64_metadata(const char * line,uint64_t * seed,unsigned * count,
    char fresh[6],uint64_t * entries) {
  const char * p=line;uint64_t n;
  if(strncmp(p,"# seed ",7)) {return 1;}p+=7;
  if(a64_decimal(&p,seed)||strncmp(p," count ",7)) {return 1;}p+=7;
  if(a64_decimal(&p,&n)||n>50000||strncmp(p," fresh ",7)) {return 1;}
  *count=(unsigned)n;p+=7;
  if(!strncmp(p,"true ",5)) {memcpy(fresh,"true",5);p+=5;}
  else if(!strncmp(p,"false ",6)) {memcpy(fresh,"false",6);p+=6;}
  else {return 1;}
  if(strncmp(p,"entries ",8)) {return 1;}p+=8;
  return a64_decimal(&p,entries)||!(*entries)||*entries>100000||*p;
}
static int a64_probe(const char * directory,int print) {
  fenv_t saved;int saved_errno=errno,status=1;
  if(fegetenv(&saved)) {return 1;}
  char path[1024],line[256];FILE * file=NULL;struct stat info;
  uint64_t seed=0,entries=0,index=0,previous=0,raw=GMATH_FNV_BASIS,state=GMATH_FNV_BASIS,calls=0;
  uint64_t generic=GMATH_FNV_BASIS,generic_count=0;
  unsigned count=0;char fresh[6];double maximum=0;
  int length=snprintf(path,sizeof path,"%s/atan-special.corpus",directory);
  if(length<0||(size_t)length>=sizeof path||stat(path,&info)||!S_ISREG(info.st_mode)||info.st_size<0||info.st_size>8*1024*1024) {goto done;}
  file=fopen(path,"rb");if(!file) {goto done;}
  if(a64_line(file,line)!=1||strcmp(line,"# Pinned oracle: atan MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1")) {goto done;}
  if(a64_line(file,line)!=1||strcmp(line,"# function atan64")) {goto done;}
  if(a64_line(file,line)!=1||a64_metadata(line,&seed,&count,fresh,&entries)) {goto done;}
  if(a64_line(file,line)!=1||strcmp(line,"# input nearest-target signed-error32 normalized-flags")) {goto done;}
  for(;;) {
    int read=a64_line(file,line);if(!read) {break;}if(read<0||strlen(line)!=44||line[16]!=' '||line[33]!=' '||line[42]!=' ') {goto done;}
    for(unsigned i=0;i<42;++i) {
      if(i==16||i==33) {continue;}
      if(!strchr("0123456789abcdef",line[i])) {goto done;}
    }
    if(!strchr("0126",line[43])) {goto done;}
    uint64_t x,target,got;uint32_t error;unsigned flag;int consumed=0;
    if(sscanf(line,"%16" SCNx64 " %16" SCNx64 " %8" SCNx32 " %u%n",&x,&target,&error,&flag,&consumed)!=4||consumed!=44||index>=entries||(index&&x<=previous)||a64_row_shape(x,target,error,flag)) {goto done;}
    previous=x;++index;
    uint64_t a=x&UINT64_C(0x7fffffffffffffff);
    int strict=a<UINT64_C(0x3e10000000000000)||a>=UINT64_C(0x4350000000000000);
    if(a64_observe(x,target,flag,strict,FE_TONEAREST,0,733,&got)) {goto done;}
    if(a64_accuracy(target,error,got,&maximum)) {
      fprintf(stderr,"atan accuracy input %016" PRIx64 " target %016" PRIx64
          " error %08" PRIx32 " got %016" PRIx64 "\n",x,target,error,got);
      goto done;
    }
    raw=gmath_fnv_u64(gmath_fnv_u64(raw,got),flag);
    if(!(a>UINT64_C(0x7ff0000000000000)&&!(x&UINT64_C(0x0008000000000000)))) {
      generic=gmath_fnv_u64(generic,got);++generic_count;
    }
    const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    unsigned subsets=a64_selected(x,index)?32u:1u;
    for(unsigned mode=0;mode<4;++mode) for(unsigned subset=0;subset<subsets;++subset) for(unsigned err=0;err<2;++err) {
      int e=err?733:0;
      if(a64_observe(x,target,flag,strict,modes[mode],subset,e,&got)) {goto done;}
      state=gmath_fnv_u64(state,got);state=gmath_fnv_u64(state,flag);state=gmath_fnv_u64(state,mode);state=gmath_fnv_u64(state,subset);state=gmath_fnv_u64(state,(uint64_t)e);++calls;
    }
  }
  if(ferror(file)||index!=entries) {goto done;}
  status=0;
done:
  if(file&&fclose(file)) {status=1;}
  if(status) {fprintf(stderr,"atan corpus invalid/accuracy/state failure from %s row%" PRIu64 "\n",directory,index);}
  else if(print) {
    if(printf("atan64 raw %016" PRIx64 " rows %" PRIu64 " state %016" PRIx64 " calls %" PRIu64 " generic %016" PRIx64 " rows %" PRIu64 " from %s seed %" PRIu64 " count %u fresh %s maximum %.9f\n",raw,index,state,calls,generic,generic_count,directory,seed,count,fresh,maximum)<0) {status=1;}
  }
  if(fesetenv(&saved)) {status=1;}
  errno=saved_errno;
  return status;
}
#endif
