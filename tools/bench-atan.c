/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Nearest-only scalar comparison on independently certified corpus members.
 */
#define _POSIX_C_SOURCE 200809L
#include "../tests/atan_corpus.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>
#define N 4096u
#ifndef GMATH_ATAN_BENCH_PAIRS
#define GMATH_ATAN_BENCH_PAIRS 401u
#endif
struct row {uint64_t x,target;uint32_t error;unsigned flags;};
static struct row pool[100000],input[N];
static unsigned population,eligible[100000];
static double (*volatile function)(double);
static volatile uint64_t sink;
static const char * ranges[]={"ordinary","direct","table","tiny-normal",
    "subnormal","wide","zero","infinity","qNaN","sNaN","reciprocal"};
static void fail(const char * message) {fprintf(stderr,"atan benchmark %s\n",message);exit(2);}
static int member(unsigned range,uint64_t x) {
  uint64_t a=x&UINT64_C(0x7fffffffffffffff);
  switch(range) {
    case 0:return a>=UINT64_C(0x3fd0000000000000)&&a<UINT64_C(0x4010000000000000);
    case 1:return a>=UINT64_C(0x3eb0000000000000)&&a<UINT64_C(0x3fc0000000000000);
    case 2:return a>=UINT64_C(0x3fc0000000000000)&&a<UINT64_C(0x3ff0000000000000);
    case 3:return a>=UINT64_C(0x0010000000000000)&&a<UINT64_C(0x3e10000000000000);
    case 4:return a&&a<UINT64_C(0x0010000000000000);
    case 5:return a>=UINT64_C(0x4350000000000000)&&a<UINT64_C(0x7ff0000000000000);
    case 6:return !a;
    case 7:return a==UINT64_C(0x7ff0000000000000);
    case 8:return a>UINT64_C(0x7ff0000000000000)&&(a&UINT64_C(0x0008000000000000));
    case 9:return a>UINT64_C(0x7ff0000000000000)&&!(a&UINT64_C(0x0008000000000000));
    default:return a>=UINT64_C(0x4010000000000000)&&a<UINT64_C(0x4350000000000000);
  }
}
static unsigned select_range(unsigned range) {
  unsigned count=0;
  for(unsigned i=0;i<population;++i) {if(member(range,pool[i].x)) {eligible[count++]=i;}}
  if(!count) {fail("empty input range");}
  unsigned split=0;
  while(split<count&&!(pool[eligible[split]].x>>63)) {++split;}
  unsigned ordered[100000],positive=0,negative=split,out=0;
  while(positive<split||negative<count) {
    if(positive<split) {ordered[out++]=eligible[positive++];}
    if(negative<count) {ordered[out++]=eligible[negative++];}
  }
  for(unsigned i=0;i<N;++i) {input[i]=pool[ordered[i%count]];}
  return count;
}
static uint64_t call(unsigned i) {
  double x,y;uint64_t got;memcpy(&x,&input[i].x,8);y=function(x);memcpy(&got,&y,8);return got;
}
static void setup(int seeded) {
  if(fesetround(FE_TONEAREST)||feclearexcept(FE_ALL_EXCEPT)||
      (seeded&&feraiseexcept(FE_UNDERFLOW|FE_INEXACT))) {fail("cannot seed state");}
  errno=seeded?733:0;
}
static uint64_t tick(void) {
  struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)) {fail("clock failure");}
  return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static int compare_u64(const void * a,const void * b) {
  uint64_t x=*(const uint64_t *)a,y=*(const uint64_t *)b;return (x>y)-(x<y);
}
static int compare_double(const void * a,const void * b) {
  double x=*(const double *)a,y=*(const double *)b;return (x>y)-(x<y);
}
static uint64_t measure(unsigned host,int seeded,int added,uint64_t wanted) {
  function=host?atan:gmath_atan;setup(seeded);
  int incoming=fetestexcept(FE_ALL_EXCEPT);uint64_t controls=gmath_test_controls();
  uint64_t hash=GMATH_FNV_BASIS,start=tick();
  for(unsigned i=0;i<N;++i) {hash=gmath_fnv_u64(hash,call(i));}
  uint64_t elapsed=tick()-start;sink^=hash;
  if(hash!=wanted) {fail("timed checksum mismatch");}
  if(fegetround()!=FE_TONEAREST||gmath_test_controls()!=controls||
      fetestexcept(FE_ALL_EXCEPT)!=(incoming|added)||(!host&&errno!=(seeded?733:0))) {
    fail("timed state mismatch");
  }
  return elapsed;
}
static void preflight(int seeded,int added[2],uint64_t hashes[2]) {
  for(unsigned host=0;host<2;++host) {
    added[host]=0;hashes[host]=GMATH_FNV_BASIS;
    for(unsigned i=0;i<N;++i) {
      uint64_t own=0;int strict=(input[i].x&UINT64_C(0x7fffffffffffffff))<UINT64_C(0x3e10000000000000)||
          (input[i].x&UINT64_C(0x7fffffffffffffff))>=UINT64_C(0x4350000000000000);
      if(!host) {
        if(a64_observe(input[i].x,input[i].target,input[i].flags,strict,FE_TONEAREST,
            seeded?24u:0u,seeded?733:0,&own)) {fail("own per-input state mismatch");}
      }
      function=host?atan:gmath_atan;setup(seeded);
      int incoming=fetestexcept(FE_ALL_EXCEPT);uint64_t controls=gmath_test_controls();
      uint64_t got=call(i);int flags=fetestexcept(FE_ALL_EXCEPT),error=errno;
      if(fegetround()!=FE_TONEAREST||gmath_test_controls()!=controls) {fail("per-input controls mismatch");}
      if(!host&&(got!=own||error!=(seeded?733:0))) {fail("own per-input value/errno mismatch");}
      uint64_t a=input[i].x&UINT64_C(0x7fffffffffffffff),g=got&UINT64_C(0x7fffffffffffffff);
      if(host&&a>UINT64_C(0x7ff0000000000000)) {
        if(g<=UINT64_C(0x7ff0000000000000)||!(g&UINT64_C(0x0008000000000000))) {fail("host NaN class mismatch");}
      } else {
        double maximum=0;
        if(a64_accuracy(input[i].target,input[i].error,got,&maximum)) {fail("per-input accuracy mismatch");}
      }
      if((flags&incoming)!=incoming) {fail("incoming flags lost");}
      added[host]|=flags&~incoming;
      hashes[host]=gmath_fnv_u64(hashes[host],got);
    }
  }
}
int main(int argc,char ** argv) {
  if(argc<2||argc>3||(argc==3&&strcmp(argv[2],"--references"))) {return 2;}
  if(a64_probe(argv[1],0)) {return 2;}
  char path[1024],line[256];int n=snprintf(path,sizeof path,"%s/atan-special.corpus",argv[1]);
  if(n<0||(size_t)n>=sizeof path) {return 2;}
  FILE * file=fopen(path,"rb");if(!file) {return 2;}
  for(unsigned i=0;i<4;++i) {if(!fgets(line,sizeof line,file)) {fail("reference header missing");}}
  while(fgets(line,sizeof line,file)) {
    if(population>=100000||sscanf(line,"%16" SCNx64 " %16" SCNx64 " %8" SCNx32 " %u",
        &pool[population].x,&pool[population].target,&pool[population].error,&pool[population].flags)!=4) {fail("reference read mismatch");}
    ++population;
  }
  if(ferror(file)||fclose(file)) {return 2;}
  if(argc==3) {
    for(unsigned range=0;range<11;++range) {
      unsigned count=select_range(range);
      printf("atan.workload %s source %u used %u\n",ranges[range],count,count<N?count:N);
      for(unsigned i=0;i<N;++i) {printf("atan.reference %s %u %016" PRIx64 " %016" PRIx64 " %08" PRIx32 " %u\n",
          ranges[range],i,input[i].x,input[i].target,input[i].error,input[i].flags);}
    }
    return fflush(stdout)?2:0;
  }
  printf("8 paired warmups;%u alternating pairs4096; nearest only; corpus member workloads\n",GMATH_ATAN_BENCH_PAIRS);
  printf("atan.identity compiler %s; comparison host-libm; host errno/NaN payload unpromised\n",__VERSION__);
  for(unsigned range=0;range<11;++range) {
    unsigned count=select_range(range);
    printf("atan.workload %s source %u used %u\n",ranges[range],count,count<N?count:N);
    for(int seeded=0;seeded<2;++seeded) {
      int added[2];uint64_t hashes[2];preflight(seeded,added,hashes);
      for(unsigned i=0;i<8;++i) {measure(0,seeded,added[0],hashes[0]);measure(1,seeded,added[1],hashes[1]);}
      uint64_t own[GMATH_ATAN_BENCH_PAIRS],host[GMATH_ATAN_BENCH_PAIRS];double ratios[GMATH_ATAN_BENCH_PAIRS];
      for(unsigned i=0;i<GMATH_ATAN_BENCH_PAIRS;++i) {
        if(i&1u) {host[i]=measure(1,seeded,added[1],hashes[1]);own[i]=measure(0,seeded,added[0],hashes[0]);}
        else {own[i]=measure(0,seeded,added[0],hashes[0]);host[i]=measure(1,seeded,added[1],hashes[1]);}
        if(!own[i]||!host[i]) {fail("zero elapsed time");}
        ratios[i]=(double)own[i]/(double)host[i];
      }
      for(unsigned i=0;i<GMATH_ATAN_BENCH_PAIRS;++i) {
        printf("atan.pair %s %s %u own %" PRIu64 " host %" PRIu64 "\n",
            ranges[range],seeded?"UF/IX":"clean",i,own[i],host[i]);
      }
      qsort(own,GMATH_ATAN_BENCH_PAIRS,sizeof *own,compare_u64);
      qsort(host,GMATH_ATAN_BENCH_PAIRS,sizeof *host,compare_u64);
      qsort(ratios,GMATH_ATAN_BENCH_PAIRS,sizeof *ratios,compare_double);
      printf("atan %s %s own %.6f host %.6f ratio %.6f %.6f %.6f\n",ranges[range],seeded?"UF/IX":"clean",
          (double)own[GMATH_ATAN_BENCH_PAIRS/2]/N,(double)host[GMATH_ATAN_BENCH_PAIRS/2]/N,
          ratios[GMATH_ATAN_BENCH_PAIRS/10],ratios[GMATH_ATAN_BENCH_PAIRS/2],ratios[(GMATH_ATAN_BENCH_PAIRS*9)/10]);
    }
  }
  return fflush(stdout)?2:0;
}
