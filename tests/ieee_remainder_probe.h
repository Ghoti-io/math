/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared C17/C++ exact remainder/quotient/state evidence; no host references.
 */
#ifndef GMATH_IEEE_REMAINDER_PROBE_H
#define GMATH_IEEE_REMAINDER_PROBE_H
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "corpus_hash.h"
#ifdef GMATH_IEEE_REMAINDER_PRIOR
#include "ieee_remainder_prior.h"
#endif
#define IR_PROVENANCE "# Pinned oracle: ieee_remainder MPFR 4.2.2 gmpy2 2.3.2"
typedef struct {uint64_t x,y,r;int q,invalid;} ir_row;
static int ir_line(FILE *f,char *s,size_t cap) {
 size_t n=0;int c;while((c=fgetc(f))!=EOF){if(!c||n+1>=cap)return -1;if(c=='\n'){s[n]=0;return 1;}s[n++]=(char)c;}return n||ferror(f)?-1:0;
}
static int ir_hex(const char *s,unsigned n,uint64_t *out) {
 uint64_t v=0;for(unsigned i=0;i<n;i++){unsigned c=(unsigned char)s[i];if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else return 0;v=(v<<4)|c;}*out=v;return 1;
}
static int ir_invalid(uint64_t x,uint64_t y,unsigned width) {
 unsigned p=width==64?52:23,eb=width==64?11:8;uint64_t sign=UINT64_C(1)<<(width-1),inf=((UINT64_C(1)<<eb)-1)<<p,quiet=UINT64_C(1)<<(p-1);
 uint64_t a=x&(sign-1),b=y&(sign-1);
 if(a>inf||b>inf)return (a>inf&&!(a&quiet))||(b>inf&&!(b&quiet));
 return a==inf||!b;
}
static int ir_policy(ir_row a,unsigned width) {
 unsigned p=width==64?52:23,eb=width==64?11:8;uint64_t sign=UINT64_C(1)<<(width-1),hidden=UINT64_C(1)<<p,inf=((UINT64_C(1)<<eb)-1)<<p;
 uint64_t x=a.x&(sign-1),y=a.y&(sign-1),r=a.r&(sign-1);
 if(a.invalid!=ir_invalid(a.x,a.y,width)||a.q< -127||a.q>127)return 0;
 if(x>=inf||y>inf||!y)return a.r==(inf|(hidden>>1))&&a.q==0;
 if(!x||y==inf)return a.r==a.x&&a.q==0;
 uint64_t half=y<2*hidden?y>>1:y-hidden;
 if(r>half||(!r&&((a.r^a.x)&sign)))return 0;
 return !a.q||((a.q<0)==!!((a.x^a.y)&sign));
}
static int ir_call(ir_row row,unsigned width,int mode,int subset,int error,int kind,uint64_t *output,int *quotient) {
 *output=0;*quotient=0;
 const int flags[5]={FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT};int incoming=0;
 for(int i=0;i<5;i++)if(subset&(1<<i))incoming|=flags[i];
 if(fesetround(mode)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(incoming))return 0;
 incoming=fetestexcept(FE_ALL_EXCEPT);errno=error;int q=INT_MIN;
 if(width==64) {
  double x,y,r;memcpy(&x,&row.x,8);memcpy(&y,&row.y,8);
  r=kind==0?gmath_remainder(x,y):gmath_remquo(x,y,kind==1?&q:NULL);
  memcpy(output,&r,8);
 } else {
  uint32_t a=(uint32_t)row.x,b=(uint32_t)row.y,v;float x,y,r;memcpy(&x,&a,4);memcpy(&y,&b,4);
  r=kind==0?gmath_remainderf(x,y):gmath_remquof(x,y,kind==1?&q:NULL);
  memcpy(&v,&r,4);*output=v;
 }
 int actual_errno=errno,actual_flags=fetestexcept(FE_ALL_EXCEPT),actual_mode=fegetround();
 if(kind==1)*quotient=q;
 int ok=*output==row.r&&(kind!=1||q==row.q)&&actual_errno==error&&actual_flags==(incoming|(row.invalid?FE_INVALID:0))&&actual_mode==mode;
#ifdef GMATH_IEEE_REMAINDER_PRIOR
 if(ok) {
  int prior_q=INT_MIN;uint64_t prior_output=0;
  if(fesetround(mode)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(incoming))return 0;
  int prior_incoming=fetestexcept(FE_ALL_EXCEPT);errno=error;
  if(width==64) {
   double x,y,r;memcpy(&x,&row.x,8);memcpy(&y,&row.y,8);
   r=kind==0?gmath_ieee_prior_remainder(x,y):gmath_ieee_prior_remquo(x,y,kind==1?&prior_q:NULL);memcpy(&prior_output,&r,8);
  } else {
   uint32_t a=(uint32_t)row.x,b=(uint32_t)row.y,v;float x,y,r;memcpy(&x,&a,4);memcpy(&y,&b,4);
   r=kind==0?gmath_ieee_prior_remainderf(x,y):gmath_ieee_prior_remquof(x,y,kind==1?&prior_q:NULL);memcpy(&v,&r,4);prior_output=v;
  }
  int prior_errno=errno,prior_flags=fetestexcept(FE_ALL_EXCEPT),prior_mode=fegetround();
  ok=prior_output==*output&&(kind!=1||prior_q==q)&&prior_incoming==incoming&&prior_errno==actual_errno&&prior_flags==actual_flags&&prior_mode==actual_mode;
  if(!ok)fprintf(stderr,"IEEE actual-prior mismatch width%u kind%d input%016" PRIx64 ",%016" PRIx64 " result%016" PRIx64 "/%016" PRIx64 " quotient%d/%d flags%x/%x errno%d/%d mode%d/%d\n",width,kind,row.x,row.y,prior_output,*output,prior_q,q,prior_flags,actual_flags,prior_errno,actual_errno,prior_mode,actual_mode);
 }
#endif
 if(!ok)fprintf(stderr,"IEEE remainder width%u kind%d input%016" PRIx64 ",%016" PRIx64 " mode%d subset%d result%016" PRIx64 "/%016" PRIx64 " quotient%d/%d flags%x/%x errno%d/%d mode%d/%d\n",width,kind,row.x,row.y,mode,subset,*output,row.r,q,row.q,actual_flags,incoming|(row.invalid?FE_INVALID:0),actual_errno,error,actual_mode,mode);
 return ok;
}
static unsigned ir_selection(uint64_t index,ir_row row,unsigned width,int subsets[32]) {
 if(index%257==0){for(int i=0;i<32;i++)subsets[i]=i;return 32;}
 unsigned p=width==64?52:23,eb=width==64?11:8;uint64_t mask=(UINT64_C(1)<<(width-1))-1,inf=((UINT64_C(1)<<eb)-1)<<p,a=row.x&mask,b=row.y&mask;
 if(index%31==0||((a>=inf||b>=inf)&&((a&((UINT64_C(1)<<p)-1))==1||b<=1))){subsets[0]=0;subsets[1]=24;subsets[2]=3;return 3;}return 0;
}
typedef struct {uint64_t raw,rows,nearest,state,calls;} ir_result;
static int ir_pinned(ir_result r,unsigned width) {
 const ir_result pins[2]={{UINT64_C(0xde2cafdcc5da3465),100316,300948,UINT64_C(0x84af9b980627e8f5),604344},{UINT64_C(0xd982af8aeb4c9bfb),31008,93024,UINT64_C(0x9f841414af40b535),203160}};
 ir_result p=pins[width==64?0:1];return r.raw==p.raw&&r.rows==p.rows&&r.nearest==p.nearest&&r.state==p.state&&r.calls==p.calls;
}
static int ir_run(const char *directory,unsigned width,int print,ir_result *record) {
 fenv_t saved;int saved_errno=errno;if(fegetenv(&saved))return 1;
 const char *name=width==64?"remainder":"remainderf";char path[4096],line[256],canonical[256];FILE *f=NULL;int status=1;
 ir_result out={GMATH_FNV_BASIS,0,0,GMATH_FNV_BASIS,0};
 if(width!=32&&width!=64)goto done;
 if(snprintf(path,sizeof path,"%s/%s-special.corpus",directory,name)>=(int)sizeof path)goto done;
 f=fopen(path,"rb");if(!f)goto done;
 if(ir_line(f,line,sizeof line)!=1||strcmp(line,IR_PROVENANCE))goto done;
 if(ir_line(f,line,sizeof line)!=1)goto done;
 if(snprintf(canonical,sizeof canonical,"# function %s",name)>=(int)sizeof canonical||strcmp(line,canonical))goto done;
 {
  char seed[21],count[6],fresh[6],entries[7],tail;int used=0;
  if(ir_line(f,line,sizeof line)!=1||sscanf(line,"# seed %20[0-9] count %5[0-9] fresh %5s entries %6[0-9]%n%c",seed,count,fresh,entries,&used,&tail)!=4||line[used]||(strcmp(fresh,"True")&&strcmp(fresh,"False")))goto done;
  if(snprintf(canonical,sizeof canonical,"# seed %s count %s fresh %s entries %s",seed,count,fresh,entries)>=(int)sizeof canonical||strcmp(canonical,line))goto done;
  errno=0;(void)strtoull(seed,NULL,10);if(errno)goto done;
  if((strlen(seed)>1&&seed[0]=='0')||(strlen(count)>1&&count[0]=='0')||(strlen(entries)>1&&entries[0]=='0'))goto done;
  if(strtoul(count,NULL,10)>50000)goto done;
  uint64_t expected=strtoull(entries,NULL,10);if(!expected||expected>500000)goto done;
  if(ir_line(f,line,sizeof line)!=1||strcmp(line,"# x y result quotient invalid"))goto done;
  uint64_t previous_x=0,previous_y=0;int read;unsigned n=width/4;
  const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  while((read=ir_line(f,line,sizeof line))==1) {
   ir_row row;char qtext[5],invalid[2];int end=0;
   if(strlen(line)<3*n+6||line[n]!=' '||line[2*n+1]!=' '||line[3*n+2]!=' '||!ir_hex(line,n,&row.x)||!ir_hex(line+n+1,n,&row.y)||!ir_hex(line+2*n+2,n,&row.r))goto done;
   if(sscanf(line+3*n+3,"%4[-0-9] %1[01]%n%c",qtext,invalid,&end,&tail)!=2||line[3*n+3+(unsigned)end])goto done;
   long q=strtol(qtext,NULL,10);if(q< -127||q>127)goto done;row.q=(int)q;row.invalid=invalid[0]-'0';
   if(snprintf(canonical,sizeof canonical,"%0*" PRIx64 " %0*" PRIx64 " %0*" PRIx64 " %d %d",(int)n,row.x,(int)n,row.y,(int)n,row.r,row.q,row.invalid)>=(int)sizeof canonical||strcmp(line,canonical)||!ir_policy(row,width))goto done;
   if(out.rows>=expected||(out.rows&&(row.x<previous_x||(row.x==previous_x&&row.y<=previous_y))))goto done;
   uint64_t r=0;int quotient=0,rawq=0;
   for(int kind=0;kind<3;kind++){if(!ir_call(row,width,FE_TONEAREST,0,0,kind,&r,&quotient))goto done;if(kind==1)rawq=quotient;++out.nearest;}
   out.raw=gmath_fnv_u64(out.raw,row.x);out.raw=gmath_fnv_u64(out.raw,row.y);out.raw=gmath_fnv_u64(out.raw,r);out.raw=gmath_fnv_u64(out.raw,(uint64_t)(int64_t)rawq);out.raw=gmath_fnv_u64(out.raw,(unsigned)row.invalid);
   int subsets[32];unsigned selections=ir_selection(out.rows,row,width,subsets);
   for(unsigned mode=0;mode<4;mode++)for(unsigned s=0;s<selections;s++)for(unsigned err=0;err<2;err++)for(int kind=0;kind<3;kind++) {
    int error=err?733:0;if(!ir_call(row,width,modes[mode],subsets[s],error,kind,&r,&quotient))goto done;
    uint64_t words[7]={out.rows,mode,(unsigned)subsets[s],(unsigned)error,(unsigned)kind,r,(uint64_t)(int64_t)quotient};
    for(unsigned i=0;i<7;i++){out.state=gmath_fnv_u64(out.state,words[i]);}
    ++out.calls;
   }
   previous_x=row.x;previous_y=row.y;++out.rows;
  }
  if(read<0||out.rows!=expected)goto done;
 }
 status=0;
 done:
 if(f)fclose(f);
 if(fesetenv(&saved))status=1;
 errno=saved_errno;
 if(!status&&record)*record=out;
 if(print&&!status)printf("ieeeraw %s %016" PRIx64 " %" PRIu64 " %" PRIu64 " %016" PRIx64 " %" PRIu64 " from %s\n",name,out.raw,out.rows,out.nearest,out.state,out.calls,directory);
 if(status)fprintf(stderr,"IEEE remainder raw/state/reference failure: %s width%u row%" PRIu64 "\n",directory,width,out.rows);
 return status;
}
#endif
