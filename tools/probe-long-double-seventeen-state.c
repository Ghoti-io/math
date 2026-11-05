/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw fixtures can exercise all adapters; fmt=0 selects the actual native ABI.
 * Public wrappers are linked from a separate production object without LTO.
 * Host libm is linked solely for test environment setup/observation. */
#define GMATH_LONG_DOUBLE_SEVENTEEN_RAW_ONLY
#include "../src/elementary/long_double_seventeen.c"
#undef GMATH_LONG_DOUBLE_SEVENTEEN_RAW_ONLY
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include "../tests/fp_controls.h"
#include "long_double_seventeen_probe_input.h"
#include "../tests/long_double_seventeen_abi.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw native(int op,ld_raw a,ld_raw b) {
 long double x,y,out;ld_write((unsigned char *)&x,a);ld_write((unsigned char *)&y,b);
#if defined(LDS17_BYTE_CALLER)
 lds17_native80_bytes(op,&x,&y,&out);
#else
 switch(op) {
 case 0:out=gmath_sinl(x);break;
 case 1:out=gmath_cosl(x);break;
 case 2:out=gmath_tanl(x);break;
 case 3:out=gmath_asinl(x);break;
 case 4:out=gmath_acosl(x);break;
 case 5:out=gmath_atanl(x);break;
 case 6:out=gmath_atan2l(x,y);break;
 case 7:out=gmath_sinhl(x);break;
 case 8:out=gmath_coshl(x);break;
 case 9:out=gmath_tanhl(x);break;
 case 10:out=gmath_asinhl(x);break;
 case 11:out=gmath_acoshl(x);break;
 case 12:out=gmath_atanhl(x);break;
 case 13:out=gmath_erfl(x);break;
 case 14:out=gmath_erfcl(x);break;
 case 15:out=gmath_tgammal(x);break;
 case 16:out=gmath_lgammal(x);break;
 default:abort();
 }
#endif
 return ld_read((const unsigned char *)&out);
}
/* MXCSR accesses require the compiler's SSE contract, including on i386.
 * FXSAVE's writable mask determines whether DAZ fixtures are supported. */
#if defined(__SSE__) && (defined(__x86_64__) || defined(__i386__))
#define LDS17_PROBE_MXCSR 1
static unsigned mxcsr_mask(void) {
  struct {unsigned char bytes[512];} __attribute__((aligned(16))) state;
  unsigned mask;__asm__ volatile("fxsave %0":"=m"(state)::"memory");
  memcpy(&mask,state.bytes+28,sizeof mask);return mask?mask:UINT32_C(0xffbf);
}
#endif
static int setup_failure(const char *reason) {
  fprintf(stderr,"seventeen state setup failed: %s\n",reason);return 2;
}
int main(void) {
  unsigned supported_mxcsr=0;
#if defined(LDS17_PROBE_MXCSR)
  supported_mxcsr=mxcsr_mask();
#endif
  printf("native %u size %zu long %zu mxcsr-mask %x\n",LD_NATIVE,sizeof(long double),sizeof(long)*CHAR_BIT,supported_mxcsr);fflush(stdout);
  unsigned rows=0;
  char line[512];
  int record=0;
  while ((record=lds17_probe_record(line,sizeof line))>0) {
    uint64_t fields[10];
    if(!lds17_probe_fields(line,fields,10,0) || fields[0]>128 || fields[1]>16 || fields[6]>3 ||
       (fields[7]!=0 && fields[7]!=2 && fields[7]!=3) || fields[8]>31 || fields[9]>3)return 2;
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1],mode=(unsigned)fields[6],pc=(unsigned)fields[7],incoming=(unsigned)fields[8];
    if(fmt && fmt!=64 && fmt!=80 && fmt!=128 && fmt!=106)return 2;
    ld_raw a={(uint64_t)fields[2],(uint64_t)fields[3]},b={(uint64_t)fields[4],(uint64_t)fields[5]};
    ++rows;
    unsigned before_mx=0,after_mx=0; unsigned short before_cw=0,after_cw=0;
    int requested_mode=(int[]){FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}[mode];
    if(feclearexcept(FE_ALL_EXCEPT) || flags())return setup_failure("clear flags");
    if(fesetround(requested_mode) || fegetround()!=requested_mode)return setup_failure("rounding mode");
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(before_cw));
    before_cw=(unsigned short)((before_cw&~0x300u)|((pc&3u)<<8));
    __asm__ volatile("fldcw %0"::"m"(before_cw));
    unsigned short check_cw;__asm__ volatile("fnstcw %0":"=m"(check_cw));
    if(check_cw!=before_cw)return setup_failure("x87 precision control");
#else
    if(pc) {fputs("unsupported x87 precision fixture\n",stderr);return 3;}
#endif
    /* Profiles preserve0=off and1=both;2=DAZ-only,3=FTZ-only. */
    unsigned profile=(unsigned)fields[9];
    unsigned profile_bits=profile==1?0x8040u:profile==2?0x40u:profile==3?0x8000u:0;
#if defined(LDS17_PROBE_MXCSR)
    if(profile_bits&~supported_mxcsr) {fputs("unsupported MXCSR control profile\n",stderr);return 3;}
    __asm__ volatile("stmxcsr %0":"=m"(before_mx));
#if LD_NATIVE == 80
    /* Deliberately disagree with native80 RC; preserve standard flags. */
    before_mx=(before_mx&~0x6000u)|(((mode+1)&3u)<<13);
#endif
    before_mx=(before_mx&~0x8040u)|profile_bits;
    __asm__ volatile("ldmxcsr %0"::"m"(before_mx));
    unsigned check_mx;__asm__ volatile("stmxcsr %0":"=m"(check_mx));
    if((check_mx&~63u)!=(before_mx&~63u))return setup_failure("MXCSR controls");
#else
    if(profile) {fputs("unsupported MXCSR control profile\n",stderr);return 3;}
    (void)profile_bits;
#endif
    if(fegetround()!=requested_mode || flags())return setup_failure("configured environment");
    int requested_flags=((incoming&1)?FE_INVALID:0)|((incoming&2)?FE_DIVBYZERO:0)|((incoming&4)?FE_INEXACT:0)|((incoming&8)?FE_UNDERFLOW:0)|((incoming&16)?FE_OVERFLOW:0);
    if(requested_flags && feraiseexcept(requested_flags))return setup_failure("seed flags");
    unsigned entry=flags();
    if((entry&incoming)!=incoming)return setup_failure("requested flags absent");
    int round_before=fegetround(); uint64_t controls_before=gmath_test_controls();
    errno=173;
    ld_raw r=!fmt?native((int)op,a,b):lds17_run(fmt,(int)op,a,b);
    int err=errno; unsigned f=flags();
    int round_after=fegetround(); uint64_t controls_after=gmath_test_controls();
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(after_cw));
#if defined(LDS17_PROBE_MXCSR)
    __asm__ volatile("stmxcsr %0":"=m"(after_mx));
#endif
#endif
    printf("%016" PRIx64 " %016" PRIx64 " %u %d %u %u\n",r.hi,r.lo,f,err,(unsigned)(round_before==round_after && controls_before==controls_after && before_cw==after_cw && (before_mx&~63u)==(after_mx&~63u)),entry); fflush(stdout);
  }
  if(record<0){fputs("long-double seventeen probe: malformed or overlong byte record\n",stderr);return 2;}
  if (ferror(stdin) || !rows) { fputs("long-double seventeen probe: input error or no rows\n",stderr);return 2; }
  return 0;
}
