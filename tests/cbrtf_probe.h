/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared C17/C++ raw Float reference and caller-state probe.
 */
#ifndef GMATH_CBRTF_PROBE_H
#define GMATH_CBRTF_PROBE_H
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "corpus_hash.h"
#define GMATH_CBRTF_PINNED_HASH UINT64_C(0xb56d6fe265757f09)
static inline int cf_pinned_modes(const uint64_t hashes[4]) {
  static const uint64_t expected[4]={UINT64_C(0x4c22f58222507773),UINT64_C(0xe8c7ee4999e8a859),UINT64_C(0xd7f9294e89e70c3b),UINT64_C(0xb207e1dd250e9dc9)};
  return !memcmp(hashes,expected,sizeof expected);
}
#ifdef GMATH_CBRTF_REFERENCE
#ifndef GMATH_CBRTF_BASELINE_IDENTITY
#error "Declared baseline identity is required for prior comparison"
#endif
#ifdef __cplusplus
extern "C" float GMATH_CBRTF_REFERENCE(float);
#else
extern float GMATH_CBRTF_REFERENCE(float);
#endif
#endif
#define CF_PROVENANCE "# Pinned oracle: tools/oracle/gen_corpus_cbrtf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1"
static float cf_value(uint32_t u) {float f;memcpy(&f,&u,4);return f;}
static uint32_t cf_bits(float f) {uint32_t u;memcpy(&u,&f,4);return u;}
static int cf_line(FILE *f,char *line,size_t cap) {
  size_t n=0;int c;
  while ((c=fgetc(f))!=EOF) {
    if (!c||n+1>=cap) return -1;
    if (c=='\n') {line[n]=0;return 1;}
    line[n++]=(char)c;
  }
  return n||ferror(f)?-1:0;
}
static int cf_hex(const char *s,unsigned n,uint32_t *out) {
  uint32_t word=0;
  for (unsigned j=0;j<n;j++) {
    unsigned c=(unsigned char)s[j],v;
    if (c>='0'&&c<='9') v=c-'0';
    else if (c>='a'&&c<='f') v=c-'a'+10;
    else return 0;
    word=(word<<4)|v;
  }
  *out=word;return 1;
}
static int cf_exponent(uint32_t a) {
  if (a>=0x00800000u) return (int)(a>>23)-127;
  int e=-126;while (a<0x00800000u) {a<<=1;--e;}return e;
}
static int cf_power(uint32_t a) {
  if (!a||a>=0x7f800000u) return 0;
  uint32_t significand=a>=0x00800000u?(a&0x007fffffu)|0x00800000u:a;
  return !(significand&(significand-1u))&&cf_exponent(a)%3==0;
}
static int cf_required(uint32_t raw) {
  uint32_t a=raw&0x7fffffffu;
  if (a>0x7f800000u) return a&0x00400000u?0:FE_INVALID;
  return !a||a==0x7f800000u||cf_power(a)?0:FE_INEXACT;
}
static unsigned cf_normalized(int f) {return ((f&FE_INVALID)?1u:0u)|((f&FE_INEXACT)?16u:0u);}
static int cf_numerical(uint32_t input,uint32_t output,uint32_t target,uint32_t error,double *maximum) {
  uint32_t a=input&0x7fffffffu,b=output&0x7fffffffu;
  if (a>=0x7f800000u||!a||cf_power(a)) return output==target;
  if ((input^output)&0x80000000u||b<0x00800000u||b>=0x7f800000u) return 0;
  int e=cf_exponent(a),q=e/3;if (e%3<0) --q;
  double unit=ldexp(1.0,q-23),ef=(double)cf_value(error);
  uint32_t ae=error&0x7fffffffu;
  double reserve=((double)cf_value(ae+1u)-(double)cf_value(ae))*0.5;
  double bound=fabs(((double)cf_value(output)-(double)cf_value(target))/unit-ef)+reserve;
  if (bound>*maximum) *maximum=bound;
  return bound<=0.51;
}
static int cf_call_with(float (*target_function)(float),const char *role,uint32_t input,int mode,int subset,int error_seed,uint32_t *output) {
  *output=0;
  const int flags[]={FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT};int incoming=0;
  for (int j=0;j<5;j++) if (subset&(1<<j)) incoming|=flags[j];
  if (fesetround(mode)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(incoming)) return 0;
  incoming=fetestexcept(FE_ALL_EXCEPT);errno=error_seed;
  float x;memcpy(&x,&input,4);float (*volatile function)(float)=target_function;
  float result=function(x);int actual_errno=errno,actual_flags=fetestexcept(FE_ALL_EXCEPT),actual_mode=fegetround();
  *output=cf_bits(result);
  int ok=actual_errno==error_seed&&actual_mode==mode&&actual_flags==(incoming|cf_required(input));
  if (!ok) fprintf(stderr,"cbrtf %s state input%08" PRIx32 " mode%d subset%d result%08" PRIx32 " flags%x expected%x errno%d/%d mode%d/%d\n",
                   role,input,mode,subset,*output,actual_flags,incoming|cf_required(input),actual_errno,error_seed,actual_mode,mode);
  return ok;
}
static int cf_call(uint32_t input,int mode,int subset,int error_seed,uint32_t *output) {
  return cf_call_with(gmath_cbrtf,"current",input,mode,subset,error_seed,output);
}
/* A verified prior-public-function witness near a nearest midpoint. Pinned
 * MPFR/mpmath and exact cube cells independently certify the nearest values.
 * This supplements (and does not alter) the committed corpus/hash population.
 */
static inline int cf_guard_witness(void) {
  static const uint32_t inputs[2]={0x236e2a8eu,0xa36e2a8eu};
  static const uint32_t expected[2][4]={{0x361d6f3eu,0x361d6f3eu,0x361d6f3fu,0x361d6f3eu},
    {0xb61d6f3eu,0xb61d6f3fu,0xb61d6f3eu,0xb61d6f3eu}};
  const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  fenv_t saved;int error=errno,status=0;if (fegetenv(&saved)) return 1;
  for (unsigned sign=0;sign<2;sign++) for (unsigned mode=0;mode<4;mode++) for (unsigned seed=0;seed<2;seed++) {
    uint32_t output;
    if (!cf_call(inputs[sign],modes[mode],seed?31:0,seed?733:0,&output)||output!=expected[sign][mode]) {
      fprintf(stderr,"cbrtf guarded midpoint input%08" PRIx32 " mode%u result%08" PRIx32 " expected%08" PRIx32 "\n",inputs[sign],mode,output,expected[sign][mode]);status=1;goto finish;
    }
#ifdef GMATH_CBRTF_REFERENCE
    uint32_t previous=0;
    if (!cf_call_with(GMATH_CBRTF_REFERENCE,"prior",inputs[sign],modes[mode],seed?31:0,seed?733:0,&previous)||previous!=output) {
      fputs("cbrtf guarded midpoint prior differs\n",stderr);status=1;goto finish;
    }
#endif
  }
 finish:
  if (fesetenv(&saved)) status=1;
  errno=error;return status;
}
static int cf_run_record(const char *directory,int print,uint64_t *result_hash,uint64_t mode_hashes[4]) {
  fenv_t saved;int saved_errno=errno;if (fegetenv(&saved)) return 1;
  char path[4096],line[256];FILE *file=NULL;int status=1;
#ifdef GMATH_CBRTF_REFERENCE
  if (GMATH_CBRTF_REFERENCE==gmath_cbrtf) {
    (void)fesetenv(&saved);errno=saved_errno;
    fputs("cbrtf reference aliases current function\n",stderr);return 1;
  }
#endif
  uint64_t hash=GMATH_FNV_BASIS,rows=0,calls=0;uint64_t modes_hash[4]={GMATH_FNV_BASIS,GMATH_FNV_BASIS,GMATH_FNV_BASIS,GMATH_FNV_BASIS};double maximum=0;
  if (snprintf(path,sizeof path,"%s/cbrtf-special.corpus",directory)>=(int)sizeof path) goto done;
  file=fopen(path,"rb");if (!file) goto done;
  if (cf_line(file,line,sizeof line)!=1||strcmp(line,CF_PROVENANCE)) goto done;
  {
    char seed[21],count[6],fresh[6],entries[8],tail;unsigned long long expected;int used=0;
    if (cf_line(file,line,sizeof line)!=1||sscanf(line,"# seed %20[0-9] count %5[0-9] fresh %5s entries %7[0-9]%n%c",seed,count,fresh,entries,&used,&tail)!=4||line[used]||
        (strcmp(fresh,"True")&&strcmp(fresh,"False"))) goto done;
    char canonical[256];
    if (snprintf(canonical,sizeof canonical,"# seed %s count %s fresh %s entries %s",seed,count,fresh,entries)>=(int)sizeof canonical||strcmp(line,canonical)) goto done;
    errno=0;(void)strtoull(seed,NULL,10);if (errno) goto done;
    if (strtoul(count,NULL,10)>50000) goto done;
    expected=strtoull(entries,NULL,10);if (!expected||expected>2000000) goto done;
    uint32_t previous=0;int read;
    while ((read=cf_line(file,line,sizeof line))==1) {
      uint32_t input,target,error,required;
      if (strlen(line)!=29||line[8]!=' '||line[17]!=' '||line[26]!=' '||
          !cf_hex(line,8,&input)||!cf_hex(line+9,8,&target)||!cf_hex(line+18,8,&error)||!cf_hex(line+27,2,&required)||
          (rows&&input<=previous)||rows>=expected) goto done;
      uint32_t a=input&0x7fffffffu,t=target&0x7fffffffu;
      if ((error&0x7fffffffu)>0x3f000000u||required!=cf_normalized(cf_required(input))) goto done;
      if (a>0x7f800000u) {if (target!=0x7fc00000u||error) goto done;}
      else if (!a||a==0x7f800000u) {if (target!=input||error) goto done;}
      else if ((input^target)&0x80000000u||t<0x00800000u||t>=0x7f800000u) goto done;
      if (cf_power(a)) {
        uint32_t exact=(input&0x80000000u)|((uint32_t)(cf_exponent(a)/3+127)<<23);
        if (target!=exact||error) goto done;
      }
      const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
      int selections=a>=0x7f800000u||cf_power(a)||rows%101==0?32:1;
      for (int m=0;m<4;m++) for (int subset=0;subset<selections;subset++) for (int err=0;err<2;err++) {
        uint32_t output;
        if (!cf_call(input,modes[m],subset,err?733:0,&output)) goto done;
#ifdef GMATH_CBRTF_REFERENCE
        uint32_t previous;
        if (!cf_call_with(GMATH_CBRTF_REFERENCE,"prior",input,modes[m],subset,err?733:0,&previous)) goto done;
        if (previous!=output) {
          fprintf(stderr,"cbrtf prior result input%08" PRIx32 " mode%d subset%d current%08" PRIx32 " prior%08" PRIx32 "\n",input,modes[m],subset,output,previous);goto done;
        }
#endif
        if (m==0) {if (!cf_numerical(input,output,target,error,&maximum)) {
          fprintf(stderr,"cbrtf numerical input%08" PRIx32 " mode%d subset%d result%08" PRIx32 " target%08" PRIx32 " error%08" PRIx32 "\n",input,modes[m],subset,output,target,error);goto done;
        }}
        else if (a>=0x7f800000u||!a||cf_power(a)) {if (output!=target) goto done;}
        else if ((input^output)&0x80000000u||(output&0x7fffffffu)<0x00800000u||(output&0x7fffffffu)>=0x7f800000u) goto done;
        if (!m&&!subset&&!err) {hash=gmath_fnv_u64(hash,output);hash=gmath_fnv_u64(hash,required);}
        if (!subset&&!err) {modes_hash[m]=gmath_fnv_u64(modes_hash[m],input);modes_hash[m]=gmath_fnv_u64(modes_hash[m],output);}
        ++calls;
      }
      previous=input;++rows;
    }
    if (read<0||rows!=expected) goto done;
  }
  status=0;
done:
  if (file) fclose(file);
  if (fesetenv(&saved)) status=1;
  errno=saved_errno;
  if (!status&&result_hash) *result_hash=hash;
  if (!status&&mode_hashes) memcpy(mode_hashes,modes_hash,sizeof modes_hash);
  if (print&&!status) printf("cbrtf.raw %016" PRIx64 " %" PRIu64 " statecalls %" PRIu64 " bound %.9f from %s\n",hash,rows,calls,maximum,directory);
  if (status) fprintf(stderr,"cbrtf raw/state/reference failure: %s row %" PRIu64 "\n",directory,rows);
  return status;
}
static inline int cf_run(const char *directory,int print) {return cf_run_record(directory,print,NULL,NULL);}
#endif
