/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Strict literal-answer native ABI client. No production adapters are used. */
#ifndef GMATH_LONG_DOUBLE_SCALE_NATIVE_H
#define GMATH_LONG_DOUBLE_SCALE_NATIVE_H
#include "long_double_native.h"
#include "fp_controls.h"
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
static ldn_raw ldsc_call(unsigned op,ldn_raw a,ldn_raw b,long n) {
  long double x,y,z;ldn_store(&x,a);ldn_store(&y,b);
  switch(op) {
    case 0:z=gmath_ldexpl(x,(int)n);break;
    case 1:z=gmath_scalbnl(x,(int)n);break;
    case 2:z=gmath_scalblnl(x,n);break;
    case 3:z=gmath_nextafterl(x,y);break;
    default:z=gmath_nexttowardl(x,y);break;
  }
  return ldn_load(&z);
}
/* Byte-counted bounded records reject NUL even at EOF; no C-string scan can
 * silently discard an embedded suffix. Return 1 record, 0 EOF, -1 invalid. */
static int ldsc_record(FILE *file,char *line,size_t capacity) {
  size_t count=0;int ch;
  while((ch=fgetc(file))!=EOF) {
    if(ch==0 || count+1>=capacity)return -1;
    line[count++]=(char)ch;
    if(ch=='\n')break;
  }
  if(ferror(file))return -1;
  line[count]=0;
  return count?1:0;
}
static uint64_t ldsc_hash_row(uint64_t hash,const uint64_t fields[13]) {
  for(unsigned i=0;i<13;++i)hash=gmath_fnv_u64(hash,fields[i]);
  return hash;
}
/* Every token is consumed and range checked before narrowing, including rows
 * belonging to another ABI. No fscanf numeric-overflow acceptance. */
static int ldsc_tokens(char *line,uint64_t fields[13],long *n) {
  char *p=line,*end;
  for(unsigned i=0;i<13;++i) {
    while(isspace((unsigned char)*p))++p;
    errno=0;
    if(i==9) {
      intmax_t value=strtoimax(p,&end,10);
      if(end==p || errno==ERANGE || value<LONG_MIN || value>LONG_MAX)return 1;
      *n=(long)value;fields[i]=(uint64_t)(int64_t)value;
    } else {
      int base=(i>=2 && i<=5)||i==10||i==11?16:10;
      if(!(base==16?isxdigit((unsigned char)*p):isdigit((unsigned char)*p)))return 1;
      uintmax_t value=strtoumax(p,&end,base);
      if(end==p || errno==ERANGE || value>UINT64_MAX)return 1;
      fields[i]=(uint64_t)value;
    }
    if(*end && !isspace((unsigned char)*end))return 1;
    p=end;
  }
  while(isspace((unsigned char)*p))++p;
  return *p!=0;
}
static int ldsc_corpus(const char *directory,int print) {
  char path[4096],line[512];snprintf(path,sizeof path,"%s/long-double-scale.corpus",directory);
  FILE *file=fopen(path,"r");if(!file)return 1;
  fenv_t saved;int saved_errno=errno;if(fegetenv(&saved)){fclose(file);return 1;}
  unsigned long populations[4]={0,0,0,0};
  uint64_t literals[4]={UINT64_C(14695981039346656037),UINT64_C(14695981039346656037),UINT64_C(14695981039346656037),UINT64_C(14695981039346656037)};
  unsigned long count=0;uint64_t hash=UINT64_C(14695981039346656037);int status=0,record=0;
  while((record=ldsc_record(file,line,sizeof line))>0) {
    uint64_t v[13];long n=0;
    if(ldsc_tokens(line,v,&n)) {status=1;break;}
    if((v[0]!=64&&v[0]!=80&&v[0]!=128&&v[0]!=106)||v[1]>4||v[6]>3||
       (v[7]!=0&&v[7]!=2&&v[7]!=3)||v[8]>31||v[12]>31||
       (v[1]<2&&(n<INT_MIN||n>INT_MAX))) {status=1;break;}
    unsigned index=v[0]==64?0:v[0]==80?1:v[0]==128?2:3;
    ++populations[index];literals[index]=ldsc_hash_row(literals[index],v);
    if(v[0]!=LDN_FORMAT)continue;
    const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    if(fesetround(modes[v[6]])||feclearexcept(FE_ALL_EXCEPT)){status=1;break;}
#if defined(__x86_64__) || defined(__i386__)
    unsigned short cw;unsigned mx;
    __asm__ volatile("fnstcw %0":"=m"(cw));cw=(unsigned short)((cw&~0x300u)|(v[7]<<8));__asm__ volatile("fldcw %0"::"m"(cw));
#if LDN_FORMAT == 80
    __asm__ volatile("stmxcsr %0":"=m"(mx));mx=(mx&~0x6000u)|(((v[6]+1)&3u)<<13);__asm__ volatile("ldmxcsr %0"::"m"(mx));
#else
    (void)mx;
#endif
#endif
    unsigned inc=(unsigned)v[8];
    if(inc)feraiseexcept(((inc&1)?FE_INVALID:0)|((inc&2)?FE_DIVBYZERO:0)|((inc&4)?FE_INEXACT:0)|((inc&8)?FE_UNDERFLOW:0)|((inc&16)?FE_OVERFLOW:0));
    uint64_t control=gmath_test_controls();int mode=fegetround();errno=173;
    ldn_raw a={v[2],v[3]},b={v[4],v[5]},got=ldsc_call((unsigned)v[1],a,b,n);int err=errno;
    int f=fetestexcept(FE_ALL_EXCEPT);
    unsigned flags=((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
    if(got.hi!=v[10]||got.lo!=v[11]||flags!=v[12]||err!=173||mode!=fegetround()||control!=gmath_test_controls()) {fprintf(stderr,"long-double scale native corpus: row %lu rejected\n",count);status=1;break;}
    v[10]=got.hi;v[11]=got.lo;v[12]=flags;hash=ldsc_hash_row(hash,v);++count;
  }
  if(record<0||ferror(file)||!feof(file)||!count)status=1;
  fclose(file);snprintf(path,sizeof path,"%s/long-double-scale.hash",directory);file=fopen(path,"r");
  if(!file)status=1;
  else {
    unsigned seen=0,matched=0,rows=0;
    while((record=ldsc_record(file,line,sizeof line))>0) {
      if(strncmp(line,"format ",7)!=0){status=1;break;}
      uintmax_t numbers[3];char *cursor=line+7,*end;int bad=0;
      for(unsigned i=0;i<3&&!bad;++i) {
        while(isspace((unsigned char)*cursor))++cursor;
        if(!(i==1?isxdigit((unsigned char)*cursor):isdigit((unsigned char)*cursor))){bad=1;break;}
        errno=0;numbers[i]=strtoumax(cursor,&end,i==1?16:10);
        if(end==cursor||errno==ERANGE||(*end&&!isspace((unsigned char)*end))){bad=1;break;}
        cursor=end;
      }
      while(isspace((unsigned char)*cursor))++cursor;
      if(bad||*cursor||numbers[0]>UINT_MAX||numbers[1]>UINT64_MAX||numbers[2]>ULONG_MAX){status=1;break;}
      unsigned fmt=(unsigned)numbers[0];uint64_t want=(uint64_t)numbers[1];unsigned long population=(unsigned long)numbers[2];
      unsigned bit=fmt==64?1:fmt==80?2:fmt==128?4:fmt==106?8:0;
      if(!bit||(seen&bit)||!population){status=1;break;}seen|=bit;++rows;
      unsigned index=fmt==64?0:fmt==80?1:fmt==128?2:3;
      if(want!=literals[index]||population!=populations[index])status=1;
      if(fmt==LDN_FORMAT) {++matched;if(want!=hash||population!=count)status=1;}
    }
    if(record<0||ferror(file)||!feof(file)||matched!=1||rows!=4||seen!=15)status=1;
    fclose(file);
  }
  if(fesetenv(&saved))status=1;
  errno=saved_errno;
  if(print)printf("math.long_double_scale.format%d.hash %016" PRIx64 "\nmath.long_double_scale.format%d.count %lu\n",LDN_FORMAT,hash,LDN_FORMAT,count);
  return status;
}
#endif
