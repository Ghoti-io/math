/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw fixtures can exercise all adapters; fmt=0 selects the actual native ABI.
 * Public wrappers are linked from a separate production object without LTO.
 * Host libm is linked solely for test environment setup/observation. */
#define GMATH_LONG_DOUBLE_NINE_RAW_ONLY
#include "../src/elementary/long_double_nine.c"
#undef GMATH_LONG_DOUBLE_NINE_RAW_ONLY
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include "../tests/fp_controls.h"
#include "../tests/long_double_nine_abi.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw native(int op,ld_raw a,ld_raw b,ld_raw c,int64_t *integer,int *q) {
 (void)q;
 long double x,y,z,out;ld_write((unsigned char *)&x,a);ld_write((unsigned char *)&y,b);ld_write((unsigned char *)&z,c);
#if defined(LD9_BYTE_CALLER)
 ld9_native80_bytes(op,&x,&y,&z,&out,q,(uint64_t *)integer);
#else
 switch(op) {
 case 0:*integer=gmath_lroundl(x);return (ld_raw){0,0};
 case 1:*integer=gmath_llroundl(x);return (ld_raw){0,0};
 case 2:*integer=gmath_lrintl(x);return (ld_raw){0,0};
 case 3:*integer=gmath_llrintl(x);return (ld_raw){0,0};
#if GMATH_HAVE_LONG_DOUBLE_REMAINDER
 case 4:out=gmath_fmodl(x,y);break;
 case 5:out=gmath_remainderl(x,y);break;
 case 6:out=gmath_remquol(x,y,q);break;
 case 9:out=gmath_remquol(x,y,0);break;
#endif
 case 7:out=gmath_fdiml(x,y);break;
 case 8:out=gmath_fmal(x,y,z);break;
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
    uintmax_t fields[12]; char *cursor=line,*end;int malformed=0;
    for (unsigned i=0;i<12 && !malformed;++i) {
      while (isspace((unsigned char)*cursor)) ++cursor;
      if (!isxdigit((unsigned char)*cursor)) {malformed=1;break;}
      errno=0;fields[i]=strtoumax(cursor,&end,16);
      if(errno==ERANGE || fields[i]>UINT64_MAX || end==cursor || (*end && !isspace((unsigned char)*end))) {malformed=1;break;}
      cursor=end;
    }
    while(isspace((unsigned char)*cursor))++cursor;
    if(malformed || *cursor || fields[0]>128 || fields[1]>9 || fields[8]>3 ||
       (fields[9]!=0 && fields[9]!=2 && fields[9]!=3) || fields[10]>31 ||
       (fields[11]!=32 && fields[11]!=64))return 2;
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1],mode=(unsigned)fields[8],pc=(unsigned)fields[9],incoming=(unsigned)fields[10];
    if(fmt && fmt!=64 && fmt!=80 && fmt!=128 && fmt!=106)return 2;
    if((fmt==106 || (!fmt && LD_NATIVE==106)) && ((op>=4 && op<=6) || op==9))return 2;
    ld_raw a={(uint64_t)fields[2],(uint64_t)fields[3]},b={(uint64_t)fields[4],(uint64_t)fields[5]},c={(uint64_t)fields[6],(uint64_t)fields[7]};
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
    __asm__ volatile("ldmxcsr %0"::"m"(before_mx));
#endif
    if (incoming) feraiseexcept(((incoming&1)?FE_INVALID:0)|((incoming&2)?FE_DIVBYZERO:0)|((incoming&4)?FE_INEXACT:0)|((incoming&8)?FE_UNDERFLOW:0)|((incoming&16)?FE_OVERFLOW:0));
    unsigned entry=flags();
    int round_before=fegetround(); uint64_t controls_before=gmath_test_controls();
    errno=173;
    int64_t integer=0;int q=0;ld_raw r={0,0};
    if(!fmt)r=native((int)op,a,b,c,&integer,&q);
    else if(op<4)integer=ldn_integer(fmt,a,op>=2,(int)mode,(unsigned)fields[11]);
    else r=ldn_run(fmt,op==9?LDN_REMQUO:(int)op-4,a,b,c,(int)mode,op==6?&q:0);
    int err=errno; unsigned f=flags();
    int round_after=fegetround(); uint64_t controls_after=gmath_test_controls();
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(after_cw));
    __asm__ volatile("stmxcsr %0":"=m"(after_mx));
#endif
    printf("%016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %u %d %u %u\n",r.hi,r.lo,(uint64_t)integer,(uint64_t)(int64_t)q,f,err,(unsigned)(round_before==round_after && controls_before==controls_after && before_cw==after_cw && (before_mx&~63u)==(after_mx&~63u)),entry); fflush(stdout);
  }
  if(record<0){fputs("long-double nine probe: malformed or overlong byte record\n",stderr);return 2;}
  if (ferror(stdin) || !rows) { fputs("long-double nine probe: input error or no rows\n",stderr);return 2; }
  return 0;
}
