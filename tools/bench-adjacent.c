/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Same-input paired indirect calls; no application speedup claim.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#if defined(GMATH_NEXTAFTER_BASELINE) != defined(GMATH_NEXTAFTERF_BASELINE)
#error "Both adjacent baseline functions must be configured together"
#endif
#ifdef GMATH_NEXTAFTER_BASELINE
#ifndef GMATH_ADJACENT_BASELINE_IDENTITY
#error "Declared baseline identity is required"
#endif
extern double GMATH_NEXTAFTER_BASELINE(double, double);
extern float GMATH_NEXTAFTERF_BASELINE(float, float);
#define ADJACENT_BASELINE_DOUBLE GMATH_NEXTAFTER_BASELINE
#define ADJACENT_BASELINE_FLOAT GMATH_NEXTAFTERF_BASELINE
#define ADJACENT_BASELINE_DESCRIPTION                                          \
  "configured separately compiled baseline (declared identity below)"
#define ADJACENT_BASELINE_LABEL "prior"
#define ADJACENT_BASELINE_PRESERVES_ERRNO 1
#else
#define ADJACENT_BASELINE_DOUBLE nextafter
#define ADJACENT_BASELINE_FLOAT nextafterf
#define ADJACENT_BASELINE_DESCRIPTION "host libm"
#define ADJACENT_BASELINE_LABEL "host"
#define ADJACENT_BASELINE_PRESERVES_ERRNO 0
#endif
#define N 4096
#define PAIRS 401
static uint64_t x[N], y[N];
static volatile uint64_t sink;
static uint64_t random_state = UINT64_C(0x61646a6163656e74);
static uint64_t random_word(void) {
  random_state ^= random_state << 13;
  random_state ^= random_state >> 7;
  random_state ^= random_state << 17;
  return random_state;
}
static double dvalue(uint64_t raw) {
  double value;
  memcpy(&value, &raw, 8);
  return value;
}
static float fvalue(uint64_t raw) {
  uint32_t word = (uint32_t)raw;
  float value;
  memcpy(&value, &word, 4);
  return value;
}
static uint64_t dbits(double value) {
  uint64_t raw;
  memcpy(&raw, &value, 8);
  return raw;
}
static uint64_t fbits(float value) {
  uint32_t raw;
  memcpy(&raw, &value, 4);
  return raw;
}
static double (*volatile double_fn)(double, double);
static float (*volatile float_fn)(float, float);
static double measure(int single, int host, int seeded) {
  double_fn = host ? ADJACENT_BASELINE_DOUBLE : gmath_nextafter;
  float_fn = host ? ADJACENT_BASELINE_FLOAT : gmath_nextafterf;
  if (feclearexcept(FE_ALL_EXCEPT) ||
      (seeded && feraiseexcept(FE_UNDERFLOW | FE_INEXACT))) {
    exit(2);
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT), error_seed = seeded ? E2BIG : 0;
  if (incoming != (seeded ? (FE_UNDERFLOW | FE_INEXACT) : 0)) {
    exit(2);
  }
  errno = error_seed;
  struct timespec start, end;
  uint64_t sum = 0;
  if (clock_gettime(CLOCK_MONOTONIC, &start)) {
    exit(2);
  }
  if (single) {
    for (int i = 0; i < N; ++i) {
      sum += fbits(float_fn(fvalue(x[i]), fvalue(y[i])));
    }
  } else {
    for (int i = 0; i < N; ++i) {
      sum += dbits(double_fn(dvalue(x[i]), dvalue(y[i])));
    }
  }
  if (clock_gettime(CLOCK_MONOTONIC, &end)) {
    exit(2);
  }
  int error = errno, flags = fetestexcept(FE_ALL_EXCEPT), mode = fegetround();
  if ((flags & incoming) != incoming || mode != FE_TONEAREST ||
      ((!host || ADJACENT_BASELINE_PRESERVES_ERRNO) && error != error_seed)) {
    exit(2);
  }
  sink = sum;
  return ((double)(end.tv_sec - start.tv_sec) * 1e9 +
          (double)(end.tv_nsec - start.tv_nsec)) /
         N;
}
static void verify(int single) {
  double (*volatile own_d)(double, double) = gmath_nextafter;
  double (*volatile host_d)(double, double) = ADJACENT_BASELINE_DOUBLE;
  float (*volatile own_f)(float, float) = gmath_nextafterf;
  float (*volatile host_f)(float, float) = ADJACENT_BASELINE_FLOAT;
  if (own_d == host_d || own_f == host_f) {
    fputs("adjacent benchmark baseline aliases current function\n", stderr);
    exit(2);
  }
  for (int i = 0; i < N; ++i) {
    uint64_t a = single ? fbits(own_f(fvalue(x[i]), fvalue(y[i])))
                        : dbits(own_d(dvalue(x[i]), dvalue(y[i])));
    uint64_t b = single ? fbits(host_f(fvalue(x[i]), fvalue(y[i])))
                        : dbits(host_d(dvalue(x[i]), dvalue(y[i])));
    if (a != b) {
      fputs("adjacent benchmark baseline-bit guard failed\n", stderr);
      exit(2);
    }
  }
}
static int compare(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
int main(void) {
  if (fesetenv(FE_DFL_ENV) || fesetround(FE_TONEAREST)) {
    return 2;
  }
  const char * names[] = {"common normal", "equality", "subnormal steps",
                          "normal boundary", "overflow/inward"};
  puts("401 alternating pairs of 4096 identical inputs; median ns/call and "
       "paired gmath/baseline p10/median/p90; "
       "indirect-call/loop/checksum/timestamp overhead included");
  puts("baseline: " ADJACENT_BASELINE_DESCRIPTION);
#ifdef GMATH_NEXTAFTER_BASELINE
  fputs(GMATH_ADJACENT_BASELINE_IDENTITY, stdout);
#endif
  for (int single = 0; single < 2; ++single) {
    unsigned m = single ? 23u : 52u, bias = single ? 127u : 1023u;
    uint64_t sign = UINT64_C(1) << (single ? 31u : 63u), minimum = UINT64_C(1)
                                                                   << m;
    uint64_t inf = (single ? UINT64_C(255) : UINT64_C(2047)) << m,
             one = (uint64_t)bias << m;
    for (int range = 0; range < 5; ++range) {
      for (int i = 0; i < N; ++i) {
        uint64_t a = random_word(), b = random_word(), sa = a & sign,
                 sb = b & sign;
        if (range == 0) {
          x[i] =
              sa | ((uint64_t)(bias - 3u + a % 7u) << m) | (a & (minimum - 1));
          y[i] =
              sb | ((uint64_t)(bias - 3u + b % 7u) << m) | (b & (minimum - 1));
        } else if (range == 1) {
          x[i] = sa | ((uint64_t)(1u + a % (2u * bias)) << m) |
                 (a & (minimum - 1));
          y[i] = x[i];
          if (i % 1024 == 0) {
            x[i] = sa;
            y[i] = sb;
          }
        } else if (range == 2) {
          x[i] = sa | (a & (minimum - 1)) | 1;
          y[i] = sb | one;
        } else if (range == 3) {
          x[i] = sa | ((i & 1) ? minimum : minimum - 1);
          y[i] = (i & 1) ? sa : sa | one;
        } else {
          x[i] = sa | ((i & 1) ? inf : inf - 1);
          y[i] = (i & 1) ? sa : sa | inf;
        }
      }
      verify(single);
      for (int seeded = 0; seeded < 2; ++seeded) {
        double own[PAIRS], host[PAIRS], ratio[PAIRS];
        for (int pair = 0; pair < PAIRS; ++pair) {
          if (pair & 1) {
            host[pair] = measure(single, 1, seeded);
            own[pair] = measure(single, 0, seeded);
          } else {
            own[pair] = measure(single, 0, seeded);
            host[pair] = measure(single, 1, seeded);
          }
          if (own[pair] <= 0 || host[pair] <= 0) {
            return 2;
          }
          ratio[pair] = own[pair] / host[pair];
        }
        qsort(own, PAIRS, sizeof(double), compare);
        qsort(host, PAIRS, sizeof(double), compare);
        qsort(ratio, PAIRS, sizeof(double), compare);
        printf("%-10s %-18s %s gmath %.3f " ADJACENT_BASELINE_LABEL
               " %.3f ratio %.3f %.3f %.3f\n",
               single ? "nextafterf" : "nextafter", names[range],
               seeded ? "UF/IX" : "clean", own[PAIRS / 2], host[PAIRS / 2],
               ratio[PAIRS / 10], ratio[PAIRS / 2], ratio[9 * PAIRS / 10]);
      }
    }
  }
  return 0;
}
