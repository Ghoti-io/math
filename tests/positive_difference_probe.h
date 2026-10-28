/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw positive-difference calls with inline actual caller-state assertions.
 */
#ifndef GMATH_TEST_POSITIVE_DIFFERENCE_PROBE_H
#define GMATH_TEST_POSITIVE_DIFFERENCE_PROBE_H
#include "corpus_hash.h"
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fp_controls.h"
static uint64_t ppd_controls(void) {return gmath_test_controls();}

static int ppd_call(uint64_t x, uint64_t y, uint64_t expected, unsigned flags,
    unsigned width, int mode, int subset, int error, uint64_t * hash,
    int ordered) {
  fenv_t saved;
  int saved_errno = errno, status = 1;
  if (fegetenv(&saved)) {return 1;}
  const int kinds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW, FE_INEXACT};
  int seed = 0;
  for (unsigned i = 0; i < 5; ++i) {
    if (subset & (1 << i)) {seed |= kinds[i];}
  }
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {goto done;}
  {
    int incoming = fetestexcept(FE_ALL_EXCEPT);
    uint64_t controls = ppd_controls(), got;
    errno = error;
    if (width == 64) {
      double a, b, out;
      memcpy(&a, &x, 8);memcpy(&b, &y, 8);
      double (*volatile fn)(double, double) = gmath_fdim;
      out = fn(a, b);memcpy(&got, &out, 8);
    } else {
      uint32_t bx = (uint32_t)x, by = (uint32_t)y, raw;
      float a, b, out;
      memcpy(&a, &bx, 4);memcpy(&b, &by, 4);
      float (*volatile fn)(float, float) = gmath_fdimf;
      out = fn(a, b);memcpy(&raw, &out, 4);got = raw;
    }
    int got_errno = errno, got_flags = fetestexcept(FE_ALL_EXCEPT);
    int got_mode = fegetround();
    int want = incoming | ((flags & 1u) ? FE_INVALID : 0) |
        ((flags & 2u) ? FE_INEXACT : 0) | ((flags & 4u) ? FE_OVERFLOW : 0);
    if (ppd_controls() != controls) {
      fputs("positive difference control-state mismatch\n", stderr);goto done;
    }
    if (got != expected || got_flags != want || got_errno != error || got_mode != mode) {
      fprintf(stderr, "positive difference mismatch width%u x%016" PRIx64
          " y%016" PRIx64 " got%016" PRIx64 "/%016" PRIx64
          " flags%x/%x errno%d/%d mode%d/%d\n", width, x, y, got,
          expected, got_flags, want, got_errno, error, got_mode, mode);
      goto done;
    }
    *hash = gmath_fnv_u64(gmath_fnv_u64(*hash, got), flags);
    if (ordered) {
      unsigned code = got_mode == FE_TONEAREST ? 0u :
          got_mode == FE_DOWNWARD ? 1u : got_mode == FE_UPWARD ? 2u : 3u;
      *hash = gmath_fnv_u64(gmath_fnv_u64(gmath_fnv_u64(*hash, code),
          (unsigned)subset), (unsigned)got_errno);
    }
    status = 0;
  }
 done:
  if (fesetenv(&saved)) {status = 1;}
  errno = saved_errno;
  return status;
}
/* Byte-counted lines reject embedded NUL and an incomplete final record. */
static int ppd_line(FILE * file, char * line, size_t capacity) {
  size_t n = 0;int c;
  while ((c = fgetc(file)) != EOF && c != '\n') {
    if (!c || n + 1 >= capacity) {return -1;}
    line[n++] = (char)c;
  }
  line[n] = 0;
  if (ferror(file)) {return -1;}
  return c == EOF ? (n ? -1 : 0) : 1;
}
static int ppd_hex(const char * text, unsigned width, uint64_t * value) {
  if (strlen(text) != width / 4) {return 0;}
  uint64_t n = 0;
  for (const char * p = text; *p; ++p) {
    unsigned d = (unsigned char)*p;
    if (d >= '0' && d <= '9') {d -= '0';}
    else if (d >= 'a' && d <= 'f') {d = d - 'a' + 10;}
    else {return 0;}
    n = (n << 4) | d;
  }
  *value = n;return 1;
}
struct ppd_meta {uint64_t seed, count, entries;int fresh;};
static int ppd_metadata(const char * line, struct ppd_meta * meta) {
  char seed[32], count[32], rows[32], fresh[6], extra;
  if (sscanf(line, "# seed %31s count %31s fresh %5s entries %31s %c",
      seed, count, fresh, rows, &extra) != 4 ||
      (strcmp(fresh, "false") && strcmp(fresh, "true"))) {return 0;}
  const char * numbers[] = {seed, count, rows};uint64_t values[3];
  for (unsigned i = 0; i < 3; ++i) {
    uint64_t n = 0;
    if (!*numbers[i]) {return 0;}
    for (const char * p = numbers[i]; *p; ++p) {
      if (*p < '0' || *p > '9' || n > (UINT64_MAX - (unsigned)(*p-'0')) / 10) {return 0;}
      n = n * 10 + (unsigned)(*p-'0');
    }
    values[i] = n;
  }
  if (values[0] > UINT32_MAX || values[1] > 50000 || values[2] < 1000 || values[2] > 400000) {return 0;}
  meta->seed=values[0];meta->count=values[1];meta->entries=values[2];meta->fresh=!strcmp(fresh,"true");return 1;
}
/* Semantic shape checks are loader validation, not an independent arithmetic
 * oracle. Complete Fraction/MPFR targets and SHA checks supply that evidence. */
static int ppd_shape(uint64_t x,uint64_t y,uint64_t r,unsigned flags,unsigned width) {
  uint64_t sign=UINT64_C(1)<<(width-1),mask=sign-1;
  uint64_t inf=width==64?UINT64_C(0x7ff0000000000000):UINT64_C(0x7f800000);
  uint64_t quiet=width==64?UINT64_C(0x0008000000000000):UINT64_C(0x00400000);
  uint64_t minimum=width==64?UINT64_C(0x0010000000000000):UINT64_C(0x00800000);
  uint64_t a=x&mask,b=y&mask;
  if (a>inf || b>inf) {
    unsigned invalid=(a>inf&&!(x&quiet))||(b>inf&&!(y&quiet));
    return r==(inf|quiet)&&flags==invalid;
  }
  uint64_t kx=(x&sign)?mask-a:sign+a,ky=(y&sign)?mask-b:sign+b;
  if ((!a&&!b)||kx<=ky) {return !r&&!flags;}
  if (a==inf||b==inf) {return r==inf&&!flags;}
  if (!r||r>inf||(r&sign)) {return 0;}
  if (r==inf) {return flags==6;}
  return r<minimum ? flags==0 : (flags==0||flags==2);
}
static int ppd_selected(uint64_t x,uint64_t y,unsigned width,uint64_t index) {
  uint64_t mask=(UINT64_C(1)<<(width-1))-1;
  uint64_t inf=width==64?UINT64_C(0x7ff0000000000000):UINT64_C(0x7f800000);
  return index%127==0||(x&mask)>=inf||(y&mask)>=inf||!(x&mask)||!(y&mask);
}
static int ppd_probe(const char * root,unsigned width,int print) {
  fenv_t saved;int saved_errno=errno,status=1,line_status;
  FILE * file=NULL;char path[4096],line[256],function[40];
  struct ppd_meta meta={0,0,0,0};
  uint64_t rows=0,calls=0,previous_x=0,previous_y=0;
  uint64_t raw=GMATH_FNV_BASIS,state=GMATH_FNV_BASIS;
  if (fegetenv(&saved)) {return 1;}
  if (width!=64&&width!=32) {goto done;}
  {
    int n=snprintf(path,sizeof path,"%s/fdim%u-special.corpus",root,width);
    if(n<0||(size_t)n>=sizeof path) {goto done;}
  }
  file=fopen(path,"rb");if(!file) {goto done;}
  if(ppd_line(file,line,sizeof line)!=1||strcmp(line,"# Pinned oracle: positive_difference MPFR 4.2.2 gmpy2 2.3.2")) {goto done;}
  (void)snprintf(function,sizeof function,"# function fdim%u",width);
  if(ppd_line(file,line,sizeof line)!=1||strcmp(line,function)) {goto done;}
  if(ppd_line(file,line,sizeof line)!=1||!ppd_metadata(line,&meta)) {goto done;}
  if(ppd_line(file,line,sizeof line)!=1||strcmp(line,"# x y nearest-result flags")) {goto done;}
  while((line_status=ppd_line(file,line,sizeof line))==1) {
    char xs[17],ys[17],rs[17],fs[4],extra;uint64_t x,y,r;unsigned flags;
    if(++rows>meta.entries||sscanf(line,"%16s %16s %16s %3s %c",xs,ys,rs,fs,&extra)!=4||
        !ppd_hex(xs,width,&x)||!ppd_hex(ys,width,&y)||!ppd_hex(rs,width,&r)) {goto done;}
    if(!strcmp(fs,"0")) {flags=0;}
    else if(!strcmp(fs,"1")) {flags=1;}
    else if(!strcmp(fs,"2")) {flags=2;}
    else if(!strcmp(fs,"6")) {flags=6;}
    else {goto done;}
    if((rows>1&&(x<previous_x||(x==previous_x&&y<=previous_y)))||!ppd_shape(x,y,r,flags,width)) {goto done;}
    previous_x=x;previous_y=y;
    if(ppd_call(x,y,r,flags,width,FE_TONEAREST,0,733,&raw,0)) {goto done;}
    {
      const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
      unsigned subsets=ppd_selected(x,y,width,rows)?32u:1u;
      for(unsigned m=0;m<4;++m)for(unsigned subset=0;subset<subsets;++subset)for(unsigned error=0;error<2;++error) {
        if(ppd_call(x,y,r,flags,width,modes[m],(int)subset,error?733:0,&state,1)) {goto done;}
        ++calls;
      }
    }
  }
  if(line_status<0||rows!=meta.entries) {goto done;}
  status=0;
 done:
  if(file&&fclose(file)) {status=1;}
  if(status) {fprintf(stderr,"positive difference corpus invalid width%u from %s\n",width,root);}
  else if(print&&printf("positive_difference%u raw %016" PRIx64 " rows %" PRIu64
      " state %016" PRIx64 " calls %" PRIu64 " from %s seed %" PRIu64
      " count %" PRIu64 " fresh %s\n",width,raw,rows,state,calls,root,meta.seed,
      meta.count,meta.fresh?"true":"false")<0) {status=1;}
  if(fesetenv(&saved)) {status=1;}
  errno=saved_errno;return status;
}
#endif
