/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact current-mode integer results with inline actual state assertions.
 */
#ifndef GMATH_TEST_CURRENT_IR_PROBE_H
#define GMATH_TEST_CURRENT_IR_PROBE_H
#include "corpus_hash.h"
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int cr_line(FILE * file, char * line, size_t size) {
  size_t n = 0;
  int c;
  while ((c = fgetc(file)) != EOF && c != '\n') {
    if (!c || n + 1 >= size) {
      return -1;
    }
    line[n++] = (char)c;
  }
  line[n] = 0;
  if (c == EOF) {
    return n ? -1 : 0;
  }
  return 1;
}
static int cr_hex(const char * text, unsigned width, uint64_t * result) {
  if (strlen(text) != width / 4) {
    return 0;
  }
  uint64_t v = 0;
  for (const char * p = text; *p; p++) {
    unsigned d = (unsigned char)*p;
    if (d >= '0' && d <= '9') {
      d -= '0';
    }
    else if (d >= 'a' && d <= 'f') {
      d = d - 'a' + 10;
    }
    else {
      return 0;
    }
    v = (v << 4) | d;
  }
  *result = v;
  return 1;
}
static int cr_metadata(const char * line, uint64_t * entries) {
  char seed[32], count[32], rows[32], fresh[6], extra;
  if (sscanf(line, "# seed %31s count %31s fresh %5s entries %31s %c", seed,
          count, fresh, rows, &extra) != 4 ||
      (strcmp(fresh, "false") && strcmp(fresh, "true"))) {
    return 0;
  }
  const char * numbers[] = {seed, count, rows};
  uint64_t values[3];
  for (unsigned i = 0; i < 3; i++) {
    uint64_t n = 0;
    for (const char * p = numbers[i]; *p; p++) {
      if (*p < '0' || *p > '9' ||
          n > (UINT64_MAX - (unsigned)(*p - '0')) / 10) {
        return 0;
      }
      n = n * 10 + (unsigned)(*p - '0');
    }
    values[i] = n;
  }
  if (values[1] > 50000 || values[2] < 1000 || values[2] > 150000) {
    return 0;
  }
  *entries = values[2];
  return 1;
}
/* Control-only snapshots. Architectural status/diagnostic fields are excluded;
 * the standard C exception flags are asserted separately. PPC covers binary
 * controls only (old mffs upper words need not describe decimal controls).
 * Unknown ports retain the C mode/flag assertions.
 */
static uint64_t cr_controls(void) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) &&           \
    (defined(__i386__) || defined(__x86_64__))
  uint32_t raw;
  __asm__ volatile("stmxcsr %0" : "=m"(raw) : : "memory");
  uint16_t x87;
  __asm__ volatile("fnstcw %0" : "=m"(x87) : : "memory");
  return ((uint64_t)x87 << 32) | (raw & UINT32_C(0xffffffc0));
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__aarch64__)
  uint64_t raw;
  __asm__ volatile("mrs %0, fpcr" : "=r"(raw) : : "memory");
  return raw;
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__s390x__)
  uint32_t raw;
  __asm__ volatile("efpc %0" : "=d"(raw) : : "memory");
  return raw & UINT32_C(0xfc000077);
#elif (defined(__GNUC__) || defined(__clang__)) &&                             \
    (defined(__powerpc__) || defined(__powerpc64__)) &&                        \
    !defined(_SOFT_FLOAT) && !defined(__NO_FPRS__) &&                          \
    !defined(_SOFT_DOUBLE) && !defined(__SOFTFP__) && !defined(__SPE__)
  double raw;
  uint64_t word;
  __asm__ volatile("mffs %0" : "=f"(raw) : : "memory");
  memcpy(&word, &raw, sizeof word);
  return word & UINT64_C(0xff);
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__sparc__) &&       \
    !defined(__SOFTFP__) && !defined(_SOFT_FLOAT)
#if defined(__arch64__)
  uint64_t raw;
  __asm__ volatile("stx %%fsr, %0" : "=m"(raw) : : "memory");
#else
  uint32_t raw;
  __asm__ volatile("st %%fsr, %0" : "=m"(raw) : : "memory");
#endif
  return raw & UINT64_C(0xcfc00000);
#else
  return 0;
#endif
}
static int cr_call(uint64_t input, uint64_t expected, unsigned flag,
    unsigned width, int wide, int mode, int subset, int error, uint64_t * hash) {
  const int flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW, FE_INEXACT};
  int seed = 0;
  for (unsigned b = 0; b < 5; b++) {
    if (subset & (1 << b)) {seed |= flags[b];}
  }
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {return 1;}
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  uint64_t controls = cr_controls(), got;
  errno = error;
  if (width == 64) {
    double x;
    memcpy(&x, &input, 8);
    if (wide) {
      long long (*volatile fn)(double) = gmath_llrint;
      got = (uint64_t)fn(x);
    }
    else {
      long (*volatile fn)(double) = gmath_lrint;
      got = (uint64_t)fn(x);
    }
  }
  else {
    uint32_t raw = (uint32_t)input;
    float x;
    memcpy(&x, &raw, 4);
    if (wide) {
      long long (*volatile fn)(float) = gmath_llrintf;
      got = (uint64_t)fn(x);
    }
    else {
      long (*volatile fn)(float) = gmath_lrintf;
      got = (uint64_t)fn(x);
    }
  }
  int got_errno = errno, got_flags = fetestexcept(FE_ALL_EXCEPT), got_mode = fegetround();
  int want = incoming | (flag == 1 ? FE_INVALID : flag == 2 ? FE_INEXACT : 0);
  if (cr_controls() != controls) {
    fprintf(stderr, "currentint control-state mismatch\n");return 1;
  }
  if (got != expected || got_flags != want || got_errno != error || got_mode != mode) {
    fprintf(stderr, "currentint mismatch width%u wide%d input%016" PRIx64
        " got%016" PRIx64 "/%016" PRIx64 " flags%x/%x errno%d/%d mode%d/%d\n",
        width, wide, input, got, expected, got_flags, want, got_errno, error, got_mode, mode);
    return 1;
  }
  *hash = gmath_fnv_u64(gmath_fnv_u64(*hash, got), flag);
  return 0;
}
static int cr_selected(uint64_t raw, unsigned width, uint64_t index) {
  unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
  unsigned field = (unsigned)((raw >> p) & (width == 64 ? 2047u : 255u));
  return index % 127 == 0 || field == 0 || field == (width == 64 ? 2047u : 255u) ||
      field == bias-1 || field == bias || field == bias+30 || field == bias+31 ||
      field == bias+62 || field == bias+63;
}
static int cr_probe(const char * directory, unsigned width, int print) {
  fenv_t saved;
  int error = errno, status = 1;
  FILE * file = NULL;
  char path[4096], line[512];
  uint64_t entries = 0, count = 0, previous = 0, hash = GMATH_FNV_BASIS,
      state = GMATH_FNV_BASIS, calls = 0;
  if (fegetenv(&saved)) {return 1;}
  if (width != 32 && width != 64) {goto done;}
  if (snprintf(path, sizeof path, "%s/currentint%u-special.corpus", directory, width) >= (int)sizeof path) {goto done;}
  file = fopen(path, "rb");
  if (!file || cr_line(file,line,sizeof line)!=1 ||
      strcmp(line,"# Pinned oracle: currentint MPFR 4.2.2 gmpy2 2.3.2")) {goto done;}
  {
    char header[80];snprintf(header,sizeof header,"# function currentint%u",width);
    if (cr_line(file,line,sizeof line)!=1 || strcmp(line,header)) {goto done;}
  }
  if (cr_line(file,line,sizeof line)!=1 || !cr_metadata(line,&entries)) {goto done;}
  if (cr_line(file,line,sizeof line)!=1 || strcmp(line,"# input four-modes each signed32-result flags signed64-result flags")) {goto done;}
  for (;;) {
    int read = cr_line(file,line,sizeof line);
    if (!read) {break;}
    if (read < 0) {goto done;}
    char * words[17], * cursor = line;
    for (unsigned i=0;i<17;i++) {
      if (!*cursor || *cursor==' ') {goto done;}
      words[i]=cursor;
      char * space=strchr(cursor,' ');
      if (i<16) {
        if (!space) {goto done;}
        *space=0;cursor=space+1;
      }
      else if (space) {goto done;}
    }
    uint64_t raw, result[8];unsigned flag[8];
    if (!cr_hex(words[0],width,&raw) || count>=entries || (count && raw<=previous)) {goto done;}
    previous=raw;count++;
    for (unsigned i=0;i<8;i++) {
      if (!cr_hex(words[1+i*2],64,&result[i]) || strlen(words[2+i*2])!=1 ||
          words[2+i*2][0]<'0' || words[2+i*2][0]>'2') {goto done;}
      flag[i]=(unsigned)(words[2+i*2][0]-'0');
      uint64_t minimum = i%2 ? UINT64_C(0x8000000000000000) : UINT64_C(0xffffffff80000000);
      if ((flag[i]==1 && result[i]!=minimum) ||
          (!(i%2) && result[i]>(uint64_t)INT32_MAX && result[i]<UINT64_C(0xffffffff80000000))) {goto done;}
    }
    /* A signed32 valid answer is the same mathematical integer/flag as
     * signed64. This also validates columns not called by LP64 long. */
    for (unsigned mode=0;mode<4;mode++) {
      unsigned small=mode*2, large=small+1;
      int fits=result[large]<=(uint64_t)INT32_MAX || result[large]>=UINT64_C(0xffffffff80000000);
      if (flag[small]!=1) {
        if (flag[large]!=flag[small] || result[small]!=result[large]) {goto done;}
      }
      else if (flag[large]!=1 && fits) {goto done;}
    }
    unsigned p=width==64?52u:23u;
    uint64_t a=raw&((UINT64_C(1)<<(width-1))-1), inf=(width==64?UINT64_C(2047):UINT64_C(255))<<p;
    for (unsigned i=0;i<8;i++) {
      if ((a>=inf && flag[i]!=1) || (!a && (result[i] || flag[i]))) {goto done;}
    }
    const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    unsigned sets=cr_selected(raw,width,count)?32u:1u;
    for (unsigned mode=0;mode<4;mode++) {
      for (unsigned subset=0;subset<sets;subset++) {
        for (unsigned err=0;err<2;err++) {
          for (unsigned wide=0;wide<2;wide++) {
            unsigned index=mode*2+(wide || LONG_MAX==INT64_MAX ? 1u:0u);
            if (cr_call(raw,result[index],flag[index],width,(int)wide,modes[mode],(int)subset,err?733:0,&state)) {goto done;}
            if (!mode && !subset && !err) {hash=gmath_fnv_u64(gmath_fnv_u64(hash,result[index]),flag[index]);}
            calls++;
          }
        }
      }
    }
  }
  if (ferror(file) || count!=entries) {goto done;}
  if (print) {
    printf("currentint.long%u.%u %016" PRIx64 " %" PRIu64 " state %016" PRIx64 " %" PRIu64 " from %s\n",
        LONG_MAX==INT64_MAX?64u:32u,width,hash,count,state,calls,directory);
  }
  status=0;
done:
  if (file) {fclose(file);}
  if (fesetenv(&saved)) {status=1;}
  errno=error;
  if (status) {fprintf(stderr,"currentint probe failed width%u from %s after%" PRIu64 " rows\n",width,directory,count);}
  return status;
}
#endif
