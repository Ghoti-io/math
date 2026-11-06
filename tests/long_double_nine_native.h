/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Literal corpus client; calls only separate public production ABI symbols. */
#ifndef GMATH_LONG_DOUBLE_NINE_NATIVE_H
#define GMATH_LONG_DOUBLE_NINE_NATIVE_H
#include "long_double_native.h"
#include "fp_controls.h"
#include "long_double_nine_abi.h"
static ldn_raw ld9_call(unsigned op,ldn_raw a,ldn_raw b,ldn_raw c,uint64_t *integer,uint64_t *q) {
  long double x,y,z,out;ldn_store(&x,a);ldn_store(&y,b);ldn_store(&z,c);
  int quotient=0;
  (void)quotient;(void)q;
#if defined(LD9_BYTE_CALLER)
  ld9_native80_bytes((int)op,&x,&y,&z,&out,&quotient,integer);
  *q=(uint64_t)(int64_t)quotient;
#else
  ldn_raw zero={0,0},bad={UINT64_MAX,UINT64_MAX};
  switch(op) {
    case 0:*integer=(uint64_t)(int64_t)gmath_lroundl(x);return zero;
    case 1:*integer=(uint64_t)(int64_t)gmath_llroundl(x);return zero;
    case 2:*integer=(uint64_t)(int64_t)gmath_lrintl(x);return zero;
    case 3:*integer=(uint64_t)(int64_t)gmath_llrintl(x);return zero;
#if GMATH_HAVE_LONG_DOUBLE_REMAINDER
    case 4:out=gmath_fmodl(x,y);break;
    case 5:out=gmath_remainderl(x,y);break;
    case 6:out=gmath_remquol(x,y,&quotient);*q=(uint64_t)(int64_t)quotient;break;
    case 9:out=gmath_remquol(x,y,NULL);break;
#endif
    case 7:out=gmath_fdiml(x,y);break;
    case 8:out=gmath_fmal(x,y,z);break;
    default:return bad;
  }
#endif
  return ldn_load(&out);
}
/* Fixed sixteen-digit lower-hex tokens, one space, mandatory LF; rejecting
 * byte framing precedes all numeric interpretation and narrowing. */
static int ld9_record(FILE *file,uint64_t *fields,unsigned count) {
  int ch=fgetc(file);if(ch==EOF)return ferror(file)?-1:0;
  for(unsigned i=0;i<count;++i) {
    uint64_t v=0;
    for(unsigned j=0;j<16;++j) {
      unsigned digit=ch>='0' && ch<='9'?(unsigned)(ch-'0'):ch>='a' && ch<='f'?(unsigned)(ch-'a'+10):16;
      if(digit>=16)return -1;
      v=(v<<4)|digit;ch=fgetc(file);
    }
    fields[i]=v;
    if(ch!=(i+1==count?'\n':' '))return -1;
    if(i+1<count)ch=fgetc(file);
  }
  return 1;
}
static int ld9_valid(const uint64_t *v) {
  return (v[0]==64||v[0]==80||v[0]==128||v[0]==106) && v[1]<=9 &&
    v[8]<4 && (v[9]==0||v[9]==2||v[9]==3) && v[10]<=31 &&
    (v[11]==32||v[11]==64) && (v[1]==0||v[1]==2||v[11]==64) && v[16]<=31;
}
#define LD9_CORPUS_MAX_BYTES (64u*1024u*1024u)
#define LD9_CORPUS_MAX_ROWS (LD9_CORPUS_MAX_BYTES/289u)
static int ld9_corpus(const char *directory,int print) {
  char path[4096];snprintf(path,sizeof path,"%s/long-double-nine.corpus",directory);
  FILE *file=fopen(path,"rb");if(!file)return 1;
  if(fseek(file,0,SEEK_END)){fclose(file);return 1;}
  long length=ftell(file);
  if(length>0 && (unsigned long)length>LD9_CORPUS_MAX_BYTES) {fputs("long-double nine: corpus byte ceiling rejected\n",stderr);fclose(file);return 1;}
  if(length<=0 || length%289 || fseek(file,0,SEEK_SET)) {fclose(file);return 1;}
  fenv_t saved;int saved_errno=errno;if(fegetenv(&saved)){fclose(file);return 1;}
  uint64_t hashes[4][2],counts[4][2]={{0}};unsigned long called=0;
  for(unsigned f=0;f<4;++f)for(unsigned w=0;w<2;++w)hashes[f][w]=GMATH_FNV_BASIS;
  int status=0,record=0;uint64_t v[17];unsigned long records=0;
  while(records<LD9_CORPUS_MAX_ROWS && (record=ld9_record(file,v,17))>0) {
    ++records;
    if(!ld9_valid(v)){status=1;break;}
    unsigned f=v[0]==64?0:v[0]==80?1:v[0]==128?2:3;
    for(unsigned w=0;w<2;++w)if((v[1]!=0&&v[1]!=2)||v[11]==32+32*w) {
      for(unsigned i=0;i<17;++i)hashes[f][w]=gmath_fnv_u64(hashes[f][w],v[i]);
      ++counts[f][w];
    }
    if(v[0]!=LDN_FORMAT || ((v[1]==0||v[1]==2)&&v[11]!=sizeof(long)*CHAR_BIT))continue;
    const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    if(fesetround(modes[v[8]])||feclearexcept(FE_ALL_EXCEPT)){status=1;break;}
#if defined(__x86_64__) || defined(__i386__)
    unsigned short cw;__asm__ volatile("fnstcw %0":"=m"(cw));
    cw=(unsigned short)((cw&~0x300u)|(v[9]<<8));__asm__ volatile("fldcw %0"::"m"(cw));
#if LDN_FORMAT == 80
    unsigned mx;__asm__ volatile("stmxcsr %0":"=m"(mx));
    mx=(mx&~0x6000u)|(((v[8]+1)&3u)<<13);__asm__ volatile("ldmxcsr %0"::"m"(mx));
#endif
#endif
    unsigned inc=(unsigned)v[10];if(inc)feraiseexcept(((inc&1)?FE_INVALID:0)|((inc&2)?FE_DIVBYZERO:0)|((inc&4)?FE_INEXACT:0)|((inc&8)?FE_UNDERFLOW:0)|((inc&16)?FE_OVERFLOW:0));
    int before=fetestexcept(FE_ALL_EXCEPT);uint64_t controls=gmath_test_controls();int mode=fegetround();errno=173;
    unsigned incoming=((before&FE_INVALID)?1u:0u)|((before&FE_DIVBYZERO)?2u:0u)|((before&FE_INEXACT)?4u:0u)|((before&FE_UNDERFLOW)?8u:0u)|((before&FE_OVERFLOW)?16u:0u);
    if((!inc && incoming) || (incoming&inc)!=inc) {fprintf(stderr,"long-double nine: invalid pre-call seed state\n");status=1;break;}
    ldn_raw a={v[2],v[3]},b={v[4],v[5]},c={v[6],v[7]};uint64_t integer=0,q=0;
    ldn_raw r=ld9_call((unsigned)v[1],a,b,c,&integer,&q);int err=errno;
    int flags=fetestexcept(FE_ALL_EXCEPT);
    unsigned actual=((flags&FE_INVALID)?1u:0u)|((flags&FE_DIVBYZERO)?2u:0u)|((flags&FE_INEXACT)?4u:0u)|((flags&FE_UNDERFLOW)?8u:0u)|((flags&FE_OVERFLOW)?16u:0u);

    /* Some targets merge flags while seeding. Compare the actual entry union. */
    unsigned want=(unsigned)v[16]|incoming;
    if(r.hi!=v[12]||r.lo!=v[13]||integer!=v[14]||q!=v[15]||actual!=want||err!=173||mode!=fegetround()||controls!=gmath_test_controls()) {
      fprintf(stderr,"long-double nine: native row %lu op%u rejected\n",called,(unsigned)v[1]);status=1;break;
    }
    ++called;
  }
  if(records==LD9_CORPUS_MAX_ROWS && fgetc(file)!=EOF)status=1;
  if(record<0||ferror(file)||!called)status=1;
  fclose(file);
  snprintf(path,sizeof path,"%s/long-double-nine.hash",directory);file=fopen(path,"rb");
  if(!file)status=1;
  else {
    unsigned seen=0;uint64_t h[4];
    while((record=ld9_record(file,h,4))>0) {
      unsigned f=h[0]==64?0:h[0]==80?1:h[0]==128?2:h[0]==106?3:4;
      unsigned w=h[1]==32?0:h[1]==64?1:2;
      if(f==4||w==2||(seen&(1u<<(2*f+w)))){status=1;break;}
      seen|=1u<<(2*f+w);
      if(h[2]!=hashes[f][w]||h[3]!=counts[f][w]||!h[3])status=1;
    }
    if(record<0||ferror(file)||seen!=255)status=1;
    fclose(file);
  }
  if(fesetenv(&saved))status=1;
  errno=saved_errno;
  if(print)printf("long-double nine: native%d long%zu %lu literal calls\n",LDN_FORMAT,sizeof(long)*CHAR_BIT,called);
  return status;
}
#endif
