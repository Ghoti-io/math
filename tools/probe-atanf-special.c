/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw unary state probe. Numerical fixtures are pinned independent references;
 * tiny identities and special constants are checked in every rounding mode.
 */
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct vector {uint32_t input,result;};
static const struct vector cases[]={
  {0x3d3fffffu,0x3d3fdc0bu},
  {0xbd3fffffu,0xbd3fdc0bu},
  {0x3d7ffffeu,0x3d7faadcu},
  {0xbd7ffffeu,0xbd7faadcu},
  {0x3e000001u,0x3dfeadd7u},
  {0xbe000001u,0xbdfeadd7u},
  {0x3e080001u,0x3e07356fu},
  {0xbe080001u,0xbe07356fu},
  {0x3f7ffffeu,0x3f490fdau},
  {0xbf7ffffeu,0xbf490fdau},
  {0x3fbfffffu,0x3f7b985eu},
  {0xbfbfffffu,0xbf7b985eu},
  {0x403fffffu,0x3f9fe0bbu},
  {0xc03fffffu,0xbf9fe0bbu},
  {0x00000000u,0x00000000u},
  {0x80000000u,0x80000000u},
  {0x00000001u,0x00000001u},
  {0x80000001u,0x80000001u},
  {0x00000003u,0x00000003u},
  {0x80000003u,0x80000003u},
  {0x007fffffu,0x007fffffu},
  {0x807fffffu,0x807fffffu},
  {0x00800000u,0x00800000u},
  {0x80800000u,0x80800000u},
  {0x307fffffu,0x307fffffu},
  {0xb07fffffu,0xb07fffffu},
  {0x30800000u,0x30800000u},
  {0xb0800000u,0xb0800000u},
  {0x3e000000u,0x3dfeadd5u},
  {0xbe000000u,0xbdfeadd5u},
  {0x3f800000u,0x3f490fdbu},
  {0xbf800000u,0xbf490fdbu},
  {0x7f7fffffu,0x3fc90fdbu},
  {0xff7fffffu,0xbfc90fdbu},
  {0x7f800000u,0x3fc90fdbu},
  {0xff800000u,0xbfc90fdbu},
  {0x7fc00000u,0x7fc00000u},
  {0xffc00000u,0x7fc00000u},
  {0x7f800001u,0x7fc00000u}, {0xff800001u,0x7fc00000u},
  {0x7fbfffffu,0x7fc00000u}, {0xffffffffu,0x7fc00000u}
};
static uint64_t word_hash(uint64_t hash,uint32_t word) {
  for (unsigned i=0;i<4;++i) {hash^=(word>>(8*i))&255u;hash*=UINT64_C(0x100000001b3);}
  return hash;
}
static uint32_t normalized(int flags) {
  return ((flags&FE_INVALID)?1u:0u)|((flags&FE_DIVBYZERO)?2u:0u)|
    ((flags&FE_OVERFLOW)?4u:0u)|((flags&FE_UNDERFLOW)?8u:0u)|((flags&FE_INEXACT)?16u:0u);
}
int main(void) {
  fenv_t saved;int original_errno=errno;if (fegetenv(&saved)) return 2;
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const int seeds[]={0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT};
  uint64_t hash=UINT64_C(0xcbf29ce484222325),all=UINT64_C(0xcbf29ce484222325);unsigned failures=0;
  for (unsigned i=0;i<sizeof cases/sizeof *cases;++i) for (unsigned m=0;m<4;++m) for (unsigned s=0;s<7;++s) {
    uint32_t raw=cases[i].input,a=raw&0x7fffffffu;float x;memcpy(&x,&raw,4);
    if (fesetround(modes[m])||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(seeds[s])) {++failures;continue;}
    int incoming=fetestexcept(FE_ALL_EXCEPT);errno=E2BIG;
    float (*volatile fn)(float)=gmath_atanf;float result=fn(x);
    int error=errno,flags=fetestexcept(FE_ALL_EXCEPT),mode=fegetround();uint32_t output;memcpy(&output,&result,4);
    int required=a>0x7f800000u?((a&0x00400000u)?0:FE_INVALID):
      a?(FE_INEXACT|(a<0x00800000u?FE_UNDERFLOW:0)):0;
    int exact=a<0x30800000u||a>=0x7f800000u||a==0x3f800000u;
    int bad=(m==0||exact)?output!=cases[i].result:
      (output&0x80000000u)!=(raw&0x80000000u)||(output&0x7fffffffu)<0x00800000u||(output&0x7fffffffu)>0x3fc90fdbu;
    if (bad||flags!=(required|incoming)||error!=E2BIG||mode!=modes[m]) {
      fprintf(stderr,"atanf raw %08" PRIx32 " mode%u seed%u: %08" PRIx32 " flags%x required%x\n",raw,m,s,output,(unsigned)flags,(unsigned)(required|incoming));++failures;
    }
    if (s==0) {all=word_hash(all,output);all=word_hash(all,normalized(flags));}
    if (m==0&&s==0) {hash=word_hash(hash,output);hash=word_hash(hash,normalized(flags));}
  }
  if (fesetenv(&saved)) ++failures;
  errno=original_errno;
  if (!failures) printf("math.atanf_special.hash %016" PRIx64 "\nmath.atanf_special.count %zu\n",hash,sizeof cases/sizeof *cases);
  if (!failures) printf("math.atanf_all_modes.hash %016" PRIx64 "\n",all);
  return failures!=0;
}
