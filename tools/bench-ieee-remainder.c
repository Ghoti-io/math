/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired exact remainder/quotient timing; not an independent numerical oracle.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
#define PAIRS 401
static const char *active_range="setup";
static double dx[N],dy[N];static float fx[N],fy[N];static volatile uint64_t sink;
static double (*volatile call64)(double,double,int *);
static float (*volatile call32)(float,float,int *);
static double own_r(double x,double y,int *q){*q=0;return gmath_remainder(x,y);}
static double host_r(double x,double y,int *q){*q=0;return remainder(x,y);}
static float own_rf(float x,float y,int *q){*q=0;return gmath_remainderf(x,y);}
static float host_rf(float x,float y,int *q){*q=0;return remainderf(x,y);}
static double own_null(double x,double y,int *q){*q=0;return gmath_remquo(x,y,NULL);}
static float own_nullf(float x,float y,int *q){*q=0;return gmath_remquof(x,y,NULL);}
static uint64_t word64(double v){uint64_t u;memcpy(&u,&v,8);return u;}
static uint32_t word32(float v){uint32_t u;memcpy(&u,&v,4);return u;}
static unsigned magnitude(int q){unsigned u=(unsigned)q;return q<0?0u-u:u;}
static uint64_t tick(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)){fprintf(stderr,"IEEE timing clock failed: %s\n",strerror(errno));exit(2);}return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;}
static uint64_t random_word(uint64_t *s){*s^=*s<<13;*s^=*s>>7;*s^=*s<<17;return *s;}
static int invalid(uint64_t x,uint64_t y,unsigned width){unsigned p=width==64?52:23,eb=width==64?11:8;uint64_t mask=(UINT64_C(1)<<(width-1))-1,inf=((UINT64_C(1)<<eb)-1)<<p,quiet=UINT64_C(1)<<(p-1);x&=mask;y&=mask;if(x>inf||y>inf)return (x>inf&&!(x&quiet))||(y>inf&&!(y&quiet));return x==inf||!y;}
static uint64_t measure(unsigned width,int host,int quo,int seeded,int need){
 call64=host?(quo==1?remquo:host_r):(quo==0?own_r:quo==1?gmath_remquo:own_null);call32=host?(quo==1?remquof:host_rf):(quo==0?own_rf:quo==1?gmath_remquof:own_nullf);
 if(fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(seeded?(FE_UNDERFLOW|FE_INEXACT):0)){fprintf(stderr,"IEEE timing setup failed width%u path%d host%d range%s seeded%d\n",width,quo,host,active_range,seeded);exit(2);}
 int incoming=fetestexcept(FE_ALL_EXCEPT),error_seed=seeded?733:0;errno=error_seed;uint64_t sum=0,start=tick();
 if(width==64){for(int i=0;i<N;i++){int q=0;double r=call64(dx[i],dy[i],&q);sum+=word64(r)+(uint64_t)(int64_t)q;}}
 else{for(int i=0;i<N;i++){int q=0;float r=call32(fx[i],fy[i],&q);sum+=word32(r)+(uint64_t)(int64_t)q;}}
 uint64_t end=tick();int flags=fetestexcept(FE_ALL_EXCEPT),error=errno,mode=fegetround();sink+=sum;
 if(mode!=FE_TONEAREST||(flags&incoming)!=incoming||(!host&&(flags!=(incoming|need)||error!=error_seed))){fprintf(stderr,"IEEE timing state failed width%u path%d host%d range%s seeded%d flags%x expected-own%x incoming%x errno%d/%d mode%d/%d\n",width,quo,host,active_range,seeded,flags,incoming|need,incoming,error,error_seed,mode,FE_TONEAREST);exit(2);}return end-start;
}
static int cmpu(const void *a,const void *b){uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;return (x>y)-(x<y);}
static int cmpd(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static int bad(const char *check,unsigned width,unsigned range,int index,uint64_t x,uint64_t y,uint64_t own,uint64_t host,uint64_t plain,uint64_t plainhost,uint64_t null_value,int ownq,int hostq){
 fprintf(stderr,"IEEE timing %s width%u range%u(%s) index%d operands%016" PRIx64 ",%016" PRIx64 " own%016" PRIx64 " host%016" PRIx64 " plain%016" PRIx64 "/%016" PRIx64 " null%016" PRIx64 " quotient%d/%d (host guarantees low3)\n",check,width,range,active_range,index,x,y,own,host,plain,plainhost,null_value,ownq,hostq);return 2;
}
int main(void){
 const char *ranges[]={"normal","half-ties","quotient-wrap","subnormal","wide-gap","zero","infinite-divisor","NaN-domain"};uint64_t state=UINT64_C(0x72656d71756f);
 printf("compiler %s; C%ld; nearest; integer timestamps\n",__VERSION__,(long)__STDC_VERSION__);
 puts("8 paired warmups;401 alternating pairs4096; clean/UF-IX errno states; median ns/call and paired p10/median/p90; timing includes call/loop/checksum/clock and amortized first exceptions; host new flags, exceptional errno/NaN payloads and unspecified NaN quotient may differ; host quotient comparison uses only guaranteed low3 bits; own remquo(NULL) is compared with host remainder, never host remquo(NULL)");
 for(unsigned width=64;width>=32;width-=32)for(unsigned range=0;range<8;range++){
  active_range=ranges[range];
  unsigned p=width==64?52:23,eb=width==64?11:8;uint64_t sign=UINT64_C(1)<<(width-1),inf=((UINT64_C(1)<<eb)-1)<<p,hidden=UINT64_C(1)<<p;int need=0;
  for(int i=0;i<N;i++){
   uint64_t z=random_word(&state),x,y,sx=z&sign,sy=random_word(&state)&sign;
   if(range<3){double a=range==0?(double)(z%1000001)/64.0:range==1?(double)(i%511)+0.5:(double)(124+i%137);double b=range==0?(double)(1+z%127):1.0;
    if(width==64){x=word64(a);y=word64(b);}else{x=word32((float)a);y=word32((float)b);}}
   else if(range==3){x=(z&(hidden-1))|1u;y=(random_word(&state)%65535u)+1u;}
   else if(range==4){x=inf-1-(z&4095u);y=(z%32767u)+1u;}
   else if(range==5){x=0;y=(width==64?UINT64_C(0x3ff0000000000000):UINT64_C(0x3f800000));}
   else if(range==6){x=z%inf;y=inf;}
   else{switch(i%4){case 0:x=inf|1u;y=inf|(hidden>>1);break;case 1:x=inf|(hidden>>1)|3u;y=0;break;case 2:x=inf;y=hidden;break;default:x=hidden;y=0;break;}}
   x|=sx;y|=sy;need|=invalid(x,y,width)?FE_INVALID:0;
   if(width==64){memcpy(&dx[i],&x,8);memcpy(&dy[i],&y,8);}else{uint32_t a=(uint32_t)x,b=(uint32_t)y;memcpy(&fx[i],&a,4);memcpy(&fy[i],&b,4);}
   int ownq=0,hostq=0;uint64_t own,host,plain,plainhost,null_value;
   if(width==64){own=word64(gmath_remquo(dx[i],dy[i],&ownq));host=word64(remquo(dx[i],dy[i],&hostq));plain=word64(gmath_remainder(dx[i],dy[i]));plainhost=word64(remainder(dx[i],dy[i]));null_value=word64(gmath_remquo(dx[i],dy[i],NULL));}
   else{own=word32(gmath_remquof(fx[i],fy[i],&ownq));host=word32(remquof(fx[i],fy[i],&hostq));plain=word32(gmath_remainderf(fx[i],fy[i]));plainhost=word32(remainderf(fx[i],fy[i]));null_value=word32(gmath_remquof(fx[i],fy[i],NULL));}
   if(own!=plain||own!=null_value)return bad("own API consistency",width,range,i,x,y,own,host,plain,plainhost,null_value,ownq,hostq);
   if((own&(sign-1))>inf){if(own!=(inf|(hidden>>1))||(host&(sign-1))<=inf||(plainhost&(sign-1))<=inf||ownq!=0)return bad("NaN/quotient class",width,range,i,x,y,own,host,plain,plainhost,null_value,ownq,hostq);}
   else{unsigned hq=magnitude(hostq),oq=magnitude(ownq);
    if(own!=host||plain!=plainhost||oq>127u||(oq&7u)!=(hq&7u)||(ownq&&((ownq<0)!=!!((x^y)&sign)))||(hostq&&((hostq<0)!=!!((x^y)&sign)))){return bad("host exact bits/low3 quotient",width,range,i,x,y,own,host,plain,plainhost,null_value,ownq,hostq);}}
  }
  for(int quo=0;quo<3;quo++)for(int seeded=0;seeded<2;seeded++){
   for(int warm=0;warm<8;warm++){(void)measure(width,warm&1,quo,seeded,need);(void)measure(width,!(warm&1),quo,seeded,need);}
   uint64_t own[PAIRS],host[PAIRS];double ratios[PAIRS];
   for(int pair=0;pair<PAIRS;pair++){if(pair&1){host[pair]=measure(width,1,quo,seeded,need);own[pair]=measure(width,0,quo,seeded,need);}else{own[pair]=measure(width,0,quo,seeded,need);host[pair]=measure(width,1,quo,seeded,need);}if(!host[pair]){fprintf(stderr,"IEEE zero duration width%u range%s path%d pair%d\n",width,active_range,quo,pair);return 2;}ratios[pair]=(double)own[pair]/(double)host[pair];}
   qsort(own,PAIRS,sizeof *own,cmpu);qsort(host,PAIRS,sizeof *host,cmpu);qsort(ratios,PAIRS,sizeof *ratios,cmpd);
   printf("ieee %s %s %s gmath %.3f %s %.3f ratio %.3f %.3f %.3f\n",quo==0?(width==32?"remainderf":"remainder"):quo==1?(width==32?"remquof":"remquo"):(width==32?"remquof_null":"remquo_null"),ranges[range],seeded?"UF/IX":"clean",(double)own[PAIRS/2]/N,quo==2?"host-remainder":"host",(double)host[PAIRS/2]/N,ratios[PAIRS/10],ratios[PAIRS/2],ratios[9*PAIRS/10]);
  }
 }
 return sink==UINT64_C(0xdeadbeef)?1:0;
}
