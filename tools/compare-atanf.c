/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Result-only compatibility with unchanged atan2f(x,1), not a reference
 * accuracy or per-call exception proof. Sticky flags may accumulate.
 */
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef GMATH_ATANF_REFERENCE
extern float GMATH_ATANF_REFERENCE(float);
#endif
static int number(const char * text,uint64_t * value) {
  char * end;errno=0;if (!*text||*text=='-'||*text=='+') return 0;
  unsigned long long result=strtoull(text,&end,0);
  if (errno||*end) return 0;
  *value=(uint64_t)result;return 1;
}
int main(int argc,char ** argv) {
  uint64_t start,end,step,signs,mode;
  if (argc!=6||!number(argv[1],&start)||!number(argv[2],&end)||!number(argv[3],&step)||
      !number(argv[4],&signs)||!number(argv[5],&mode)||start>=end||end>UINT64_C(0x7f800000)||
      !step||step>UINT32_MAX||signs<1||signs>3||mode>3) {
    fputs("usage: compare-atanf START END STEP SIGNS(1=positive,2=negative,3=both) MODE(0=nearest,1=down,2=up,3=towardzero)\n",stderr);return 2;
  }
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  fenv_t saved;if (fegetenv(&saved)||fesetround(modes[mode])) return 2;
  float (*volatile candidate)(float)=gmath_atanf;
#ifdef GMATH_ATANF_REFERENCE
  float (*volatile previous)(float)=GMATH_ATANF_REFERENCE;
#else
  float (*volatile previous)(float,float)=gmath_atan2f;
#endif
  uint64_t count=0;int failure=0,ending_mode;
  for (uint64_t word=start;word<end;word+=step) for (unsigned sign=0;sign<2;++sign) {
    if (!(signs&(UINT64_C(1)<<sign))) continue;
    uint32_t raw=(uint32_t)word|(sign<<31);float x;memcpy(&x,&raw,4);
    float a=candidate(x);
#ifdef GMATH_ATANF_REFERENCE
    float b=previous(x);
#else
    float b=previous(x,1.0f);
#endif
    uint32_t aw,bw;memcpy(&aw,&a,4);memcpy(&bw,&b,4);
    if (aw!=bw) {fprintf(stderr,"atanf mismatch input%08" PRIx32 " candidate%08" PRIx32 " previous%08" PRIx32 "\n",raw,aw,bw);failure=1;goto done;}
    ++count;
  }
 done:
  ending_mode=fegetround();
  if (fesetenv(&saved)||ending_mode!=modes[mode]) failure=1;
  if (!failure) printf("atanf.compare %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",start,end,step,signs,mode,count);
  return failure;
}
