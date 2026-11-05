/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw fixtures can exercise all adapters; fmt=0 selects the actual native ABI.
 * Public wrappers are linked from a separate production object without LTO.
 * Host libm is linked solely for test environment setup/observation. */
#define GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
#include "../src/elementary/long_double_eleven.c"
#undef GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include "../tests/fp_controls.h"
#include "../tests/long_double_eleven_abi.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw native(int op,ld_raw a,ld_raw b) {
 long double x,y,out;ld_write((unsigned char *)&x,a);ld_write((unsigned char *)&y,b);
#if defined(LDE_BYTE_CALLER)
 lde_native80_bytes(op,&x,&y,&out);
#else
 switch(op) {
 case 0:out=gmath_sqrtl(x);break;
 case 1:out=gmath_cbrtl(x);break;
 case 2:out=gmath_hypotl(x,y);break;
 case 3:out=gmath_expl(x);break;
 case 4:out=gmath_exp2l(x);break;
 case 5:out=gmath_expm1l(x);break;
 case 6:out=gmath_logl(x);break;
 case 7:out=gmath_log2l(x);break;
 case 8:out=gmath_log10l(x);break;
 case 9:out=gmath_log1pl(x);break;
 case 10:out=gmath_powl(x,y);break;
 default:abort();
 }
#endif
 return ld_read((const unsigned char *)&out);
}
static int probe_record(char *line,size_t capacity) {
  size_t count=0;int ch;
  while((ch=fgetc(stdin))!=EOF) {
    if(ch==0 || count+1>=capacity)return -1;
    line[count++]=(char)ch;
    if(ch=='\n')break;
  }
  if(ferror(stdin))return -1;
  if(count && line[count-1]!='\n')return -1;
  line[count]=0;return count?1:0;
}
int main(void) {
  printf("native %u size %zu long %zu\n",LD_NATIVE,sizeof(long double),sizeof(long)*CHAR_BIT); fflush(stdout);
  unsigned rows=0;
  char line[512];
  int record=0;
  while ((record=probe_record(line,sizeof line))>0) {
    uintmax_t fields[10]; char *cursor=line,*end;int malformed=0;
    for (unsigned i=0;i<10 && !malformed;++i) {
      while (isspace((unsigned char)*cursor)) ++cursor;
      if (!isxdigit((unsigned char)*cursor)) {malformed=1;break;}
      errno=0;fields[i]=strtoumax(cursor,&end,16);
      if(errno==ERANGE || fields[i]>UINT64_MAX || end==cursor || (*end && !isspace((unsigned char)*end))) {malformed=1;break;}
      cursor=end;
    }
    while(isspace((unsigned char)*cursor))++cursor;
    if(malformed || *cursor || fields[0]>128 || fields[1]>10 || fields[6]>3 ||
       (fields[7]!=0 && fields[7]!=2 && fields[7]!=3) || fields[8]>31 || fields[9]>1)return 2;
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1],mode=(unsigned)fields[6],pc=(unsigned)fields[7],incoming=(unsigned)fields[8];
    if(fmt && fmt!=64 && fmt!=80 && fmt!=128 && fmt!=106)return 2;
    ld_raw a={(uint64_t)fields[2],(uint64_t)fields[3]},b={(uint64_t)fields[4],(uint64_t)fields[5]};
    ++rows;
    unsigned before_mx=0,after_mx=0; unsigned short before_cw=0,after_cw=0;
    feclearexcept(FE_ALL_EXCEPT);
    fesetround((int[]){FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}[mode]);
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(before_cw));
    before_cw=(unsigned short)((before_cw&~0x300u)|((pc&3u)<<8));
    __asm__ volatile("fldcw %0"::"m"(before_cw));
    __asm__ volatile("stmxcsr %0":"=m"(before_mx));
    /* Deliberately disagree with native80 RC; preserve standard flags. */
    #if LD_NATIVE == 80
    before_mx=(before_mx&~0x6000u)|(((mode+1)&3u)<<13);
#endif
    if(fields[9])before_mx|=0x8040u;else before_mx&=~0x8040u;
    __asm__ volatile("ldmxcsr %0"::"m"(before_mx));
#endif
    if (incoming) feraiseexcept(((incoming&1)?FE_INVALID:0)|((incoming&2)?FE_DIVBYZERO:0)|((incoming&4)?FE_INEXACT:0)|((incoming&8)?FE_UNDERFLOW:0)|((incoming&16)?FE_OVERFLOW:0));
    unsigned entry=flags();
    int round_before=fegetround(); uint64_t controls_before=gmath_test_controls();
    errno=173;
    ld_raw r=!fmt?native((int)op,a,b):lde_run(fmt,(int)op,a,b);
    int err=errno; unsigned f=flags();
    int round_after=fegetround(); uint64_t controls_after=gmath_test_controls();
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(after_cw));
    __asm__ volatile("stmxcsr %0":"=m"(after_mx));
#endif
    printf("%016" PRIx64 " %016" PRIx64 " %u %d %u %u\n",r.hi,r.lo,f,err,(unsigned)(round_before==round_after && controls_before==controls_after && before_cw==after_cw && (before_mx&~63u)==(after_mx&~63u)),entry); fflush(stdout);
  }
  if(record<0){fputs("long-double eleven probe: malformed or overlong byte record\n",stderr);return 2;}
  if (ferror(stdin) || !rows) { fputs("long-double eleven probe: input error or no rows\n",stderr);return 2; }
  return 0;
}
