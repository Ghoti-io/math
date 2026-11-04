/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw fixtures can exercise all adapters; fmt=0 selects the actual native ABI.
 * Public wrappers are linked from a separate production object without LTO.
 * Host libm is linked solely for test environment setup/observation. */
#define GMATH_LONG_DOUBLE_SCALE_RAW_ONLY
#include "../src/elementary/long_double_scale.c"
#undef GMATH_LONG_DOUBLE_SCALE_RAW_ONLY
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include "../tests/fp_controls.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw native(int op,ld_raw a,ld_raw b,long n) {
 long double x,y,z;ld_write((unsigned char *)&x,a);ld_write((unsigned char *)&y,b);
 switch(op) {
 case 0:z=gmath_ldexpl(x,(int)n);break;
 case 1:z=gmath_scalbnl(x,(int)n);break;
 case 2:z=gmath_scalblnl(x,n);break;
 case 3:z=gmath_nextafterl(x,y);break;
 default:z=gmath_nexttowardl(x,y);break;
 }
 return ld_read((const unsigned char *)&z);
}
static int probe_record(char *line,size_t capacity) {
  size_t count=0;int ch;
  while((ch=fgetc(stdin))!=EOF) {
    if(ch==0 || count+1>=capacity)return -1;
    line[count++]=(char)ch;
    if(ch=='\n')break;
  }
  if(ferror(stdin))return -1;
  line[count]=0;return count?1:0;
}
int main(void) {
  printf("native %u size %zu long %zu\n",LD_NATIVE,sizeof(long double),sizeof(long)*CHAR_BIT); fflush(stdout);
  unsigned rows=0;
  char line[512];
  int record=0;
  while ((record=probe_record(line,sizeof line))>0) {
    uintmax_t fields[9]; char *cursor=line,*end;
    int malformed=0;
    for (unsigned i=0;i<9 && !malformed;++i) {
      while (isspace((unsigned char)*cursor)) ++cursor;
      int base=i>=2 && i<=5 ? 16 : 10;
      if (!(base==16 ? isxdigit((unsigned char)*cursor) : isdigit((unsigned char)*cursor))) { malformed=1;break; }
      errno=0;fields[i]=strtoumax(cursor,&end,base);
      if (errno==ERANGE || end==cursor || (*end && !isspace((unsigned char)*end))) { malformed=1;break; }
      cursor=end;
    }
    while (isspace((unsigned char)*cursor)) ++cursor;
    errno=0;intmax_t n=0;
    if (!malformed) {
      n=strtoimax(cursor,&end,10);
      if(end==cursor || errno==ERANGE || n<LONG_MIN || n>LONG_MAX)malformed=1;
      cursor=end;while(isspace((unsigned char)*cursor))++cursor;
    }
    if (malformed || *cursor) {
      fputs("long-double probe: malformed or truncated row\n",stderr);return 2;
    }
    if ((fields[0]!=0 && fields[0]!=64 && fields[0]!=80 && fields[0]!=128 && fields[0]!=106) ||
        fields[1]>4 || fields[6]>=4 || (fields[7]!=0 && fields[7]!=2 && fields[7]!=3) || fields[8]>31 ||
        fields[2]>UINT64_MAX || fields[3]>UINT64_MAX || fields[4]>UINT64_MAX || fields[5]>UINT64_MAX) {
      fputs("long-double probe: invalid row fields\n",stderr);return 2;
    }
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1],mode=(unsigned)fields[6],pc=(unsigned)fields[7],incoming=(unsigned)fields[8];
    ld_raw a={(uint64_t)fields[2],(uint64_t)fields[3]},b={(uint64_t)fields[4],(uint64_t)fields[5]};
    ++rows;
    if(op<2 && (n<INT_MIN || n>INT_MAX)) {fputs("long-double scale probe: int exponent out of range\n",stderr);return 2;}
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
    __asm__ volatile("ldmxcsr %0"::"m"(before_mx));
#endif
    if (incoming) feraiseexcept(((incoming&1)?FE_INVALID:0)|((incoming&2)?FE_DIVBYZERO:0)|((incoming&4)?FE_INEXACT:0)|((incoming&8)?FE_UNDERFLOW:0)|((incoming&16)?FE_OVERFLOW:0));
    int round_before=fegetround(); uint64_t controls_before=gmath_test_controls();
    errno=173;
    ld_raw r=fmt ? lds_run(fmt,(int)op,a,b,(long)n) : native((int)op,a,b,(long)n);
    int err=errno; unsigned f=flags();
    int round_after=fegetround(); uint64_t controls_after=gmath_test_controls();
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(after_cw));
    __asm__ volatile("stmxcsr %0":"=m"(after_mx));
#endif
    printf("%016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %d %u %d %u\n",r.hi,r.lo,UINT64_C(0),UINT64_C(0),0,f,err,(unsigned)(round_before==round_after && controls_before==controls_after && before_cw==after_cw && (before_mx&~63u)==(after_mx&~63u))); fflush(stdout);
  }
  if(record<0){fputs("long-double probe: malformed or overlong byte record\n",stderr);return 2;}
  if (ferror(stdin) || !rows) { fputs("long-double probe: input error or no rows\n",stderr);return 2; }
  return 0;
}
