/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * All full-width references checked under nearest; boundary/raw subsets
 * checked in every mode and with all incoming flag classes. Integer result
 * hashes have width-specific expectations for native long.
 */
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../tests/corpus_hash.h"

static int selected(uint64_t raw,unsigned width,uint64_t index) {
  unsigned mantissa=width==64?52u:23u,bias=width==64?1023u:127u,maximum=width==64?2047u:255u;
  unsigned field=(unsigned)(raw>>mantissa)&maximum;
  return index%251u==0||field==0||field==maximum||field==bias-1||field==bias||field==bias+30||
      field==bias+31||field==bias+62||field==bias+63||field==bias+64;
}
static int invoke(uint64_t raw,unsigned width,unsigned wide,uint64_t expected,int invalid,int mode,int seed,
                  uint64_t * nearest,uint64_t * all,unsigned hash_kind) {
  double d=0;float f=0;
  if (width==64) memcpy(&d,&raw,8);else {uint32_t word=(uint32_t)raw;memcpy(&f,&word,4);}
  if (fesetround(mode)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(seed)) return 1;
  int incoming=fetestexcept(FE_ALL_EXCEPT);errno=E2BIG;int64_t result;
  if (wide) {
    if (width==64) {long long (*volatile fn)(double)=gmath_llround;result=fn(d);}
    else {long long (*volatile fn)(float)=gmath_llroundf;result=fn(f);}
  } else {
    if (width==64) {long (*volatile fn)(double)=gmath_lround;result=fn(d);}
    else {long (*volatile fn)(float)=gmath_lroundf;result=fn(f);}
  }
  int error=errno,flags=fetestexcept(FE_ALL_EXCEPT),rounding=fegetround();
  if ((uint64_t)result!=expected||flags!=(incoming|(invalid?FE_INVALID:0))||error!=E2BIG||rounding!=mode) {
    fprintf(stderr,"intround%u/%u input%016" PRIx64 " result%016" PRIx64 " expected%016" PRIx64 " flags%x\n",width,wide,raw,(uint64_t)result,expected,(unsigned)flags);return 1;
  }
  if (hash_kind==1) *nearest=gmath_fnv_u64(gmath_fnv_u64(*nearest,(uint64_t)result),(uint64_t)invalid);
  if (hash_kind==2) *all=gmath_fnv_u64(gmath_fnv_u64(*all,(uint64_t)result),(uint64_t)invalid);
  return 0;
}
int main(int argc,char ** argv) {
  if (argc>2) return 2;
  const char * directory=argc==2?argv[1]:"tests/corpus";
  fenv_t saved;if (fegetenv(&saved)) return 2;int saved_errno=errno;
  uint64_t nearest=GMATH_FNV_BASIS,all=GMATH_FNV_BASIS,count=0,states=0;int failure=0;
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const int seeds[]={0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT};
  for (unsigned family=0;family<2&&!failure;++family) {
    unsigned width=family==0?64u:32u;char path[4096],line[512];
    int size=snprintf(path,sizeof path,"%s/intround%u.corpus",directory,width);
    if (size<0||(size_t)size>=sizeof path) {failure=1;break;}
    FILE * input=fopen(path,"r");if (!input) {perror(path);failure=1;break;}
    uint64_t index=0;
    while (fgets(line,sizeof line,input)) {
      if (line[0]=='#') continue;
      uint64_t raw,a,b;unsigned ia,ib;char extra;
      if (sscanf(line,"%" SCNx64 " %" SCNx64 " %u %" SCNx64 " %u %c",&raw,&a,&ia,&b,&ib,&extra)!=5||ia>1||ib>1) {failure=1;break;}
      uint64_t native=LONG_MAX==INT32_MAX?a:b;int invalid_native=LONG_MAX==INT32_MAX?(int)ia:(int)ib;
      for (unsigned wide=0;wide<2;++wide) {
        failure|=invoke(raw,width,wide,wide?b:native,wide?(int)ib:invalid_native,FE_TONEAREST,0,&nearest,&all,1);++count;
      }
      if (selected(raw,width,index)) {
        for (unsigned m=0;m<4;++m) for (unsigned s=0;s<7;++s) for (unsigned wide=0;wide<2;++wide) {
          failure|=invoke(raw,width,wide,wide?b:native,wide?(int)ib:invalid_native,modes[m],seeds[s],&nearest,&all,s==0?2u:0u);++states;
        }
      }
      ++index;
      if (failure) break;
    }
    if (ferror(input)||index<4000) failure=1;
    fclose(input);
  }
  if (fesetenv(&saved)) failure=1;
  errno=saved_errno;
  if (!failure) printf("math.intround_long.bits %u\nmath.intround_full.hash %016" PRIx64 "\nmath.intround_full.count %" PRIu64 "\nmath.intround_all_modes.hash %016" PRIx64 "\nmath.intround_state.count %" PRIu64 "\n",LONG_MAX==INT32_MAX?32u:64u,nearest,count,all,states);
  return failure;
}
