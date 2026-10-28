/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Enumerate the production seed domain; compare inputs nearest both sides of
 * each admission threshold with the actual prior API. This is compatibility,
 * not an independent mathematical accuracy certificate.
 */
#include "../tests/cbrtf_probe.h"
#ifndef GMATH_CBRTF_REFERENCE
#error "Actual prior reference required"
#endif
static float (*current_api)(float)=gmath_cbrtf;
/* Include the actual production seed rather than maintaining another copy.
 * The included public function has a distinct unused name; API comparisons
 * below call the separately linked current archive and prior object.
 */
#undef gmath_cbrtf
#define gmath_cbrtf cbrtf_boundary_unused
#include "../src/elementary/float_cbrt.c"
#undef gmath_cbrtf
struct choice {uint32_t fraction;uint64_t distance;};
static int compare(uint32_t fraction,int r,int mode,uint64_t *count) {
  const int qs[3]={-42,0,r==2?41:42};
  for (unsigned k=0;k<3;k++) for (unsigned sign=0;sign<2;sign++) {
    uint32_t input=((uint32_t)(3*qs[k]+r+127)<<23)|fraction|(sign<<31),a=0,b=0;
    if (!cf_call_with(current_api,"current",input,mode,0,0,&a)||
        !cf_call_with(GMATH_CBRTF_REFERENCE,"prior",input,mode,0,0,&b)||a!=b) {
      fprintf(stderr,"cbrtf boundary input%08" PRIx32 " mode%d current%08" PRIx32 " prior%08" PRIx32 "\n",input,mode,a,b);return 1;
    }
    ++*count;
  }
  return 0;
}
int main(void) {
  fenv_t saved;int old_errno=errno,status=1;if(fegetenv(&saved))return 2;
  const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const uint64_t thresholds[2]={UINT64_C(0x00800000),UINT64_C(0x0f800000)};
  uint64_t scanned=0,compared=0,classes=0;
  for (unsigned m=0;m<4;m++) for (int r=0;r<3;r++) {
    struct choice best[64][2][2];
    for(unsigned j=0;j<64;j++)for(unsigned t=0;t<2;t++)for(unsigned side=0;side<2;side++)best[j][t][side]=(struct choice){0,UINT64_MAX};
    if(fesetround(modes[m]))goto done;
    for(uint32_t fraction=0;fraction<0x00800000u;fraction++) {
      uint64_t bits=gmath_bits(fc_seed(0x00800000u|fraction,r));
      uint64_t residue=bits&UINT64_C(0x0fffffff);unsigned j=fraction>>17;
      for(unsigned t=0;t<2;t++) {
        unsigned side=residue>thresholds[t];
        uint64_t distance=side?residue-thresholds[t]:thresholds[t]-residue;
        if(distance<best[j][t][side].distance)best[j][t][side]=(struct choice){fraction,distance};
      }
      ++scanned;
    }
    for(unsigned j=0;j<64;j++) {
      for(unsigned t=0;t<2;t++)for(unsigned side=0;side<2;side++) {
        if(best[j][t][side].distance==UINT64_MAX) {fputs("cbrtf boundary threshold class absent\n",stderr);goto done;}
        ++classes;if(compare(best[j][t][side].fraction,r,modes[m],&compared))goto done;
      }
      /* Table and outer normalized-binade endpoints, including fractions
       * whose performance prefilter chooses the old kernel directly. */
      if(compare(j<<17,r,modes[m],&compared)||compare((j<<17)|0x1ffffu,r,modes[m],&compared))goto done;
    }
  }
  if(scanned!=UINT64_C(100663296)||classes!=3072||compared!=27648)goto done;
  fputs(GMATH_CBRTF_BASELINE_IDENTITY,stdout);
  printf("cbrtf.boundaries scanned %" PRIu64 " thresholdclasses %" PRIu64 " comparisons %" PRIu64 "\n",scanned,classes,compared);status=0;
 done:
  if(fesetenv(&saved))status=1;
  errno=old_errno;return status;
}
