/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Same-input paired calls; includes call/loop/checksum/timestamp overhead.
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
#define N 4096
#define PAIRS 401
static double dx[N];
static float fx[N];
static double (*volatile df)(double, double *);
static float (*volatile ff)(float, float *);
static volatile uint64_t sink;
static uint64_t random_word(uint64_t * r) {
  *r ^= *r << 13;
  *r ^= *r >> 7;
  *r ^= *r << 17;
  return *r;
}
static uint64_t dbits(double d) {
  uint64_t u;
  memcpy(&u, &d, 8);
  return u;
}
static uint32_t fbits(float f) {
  uint32_t u;
  memcpy(&u, &f, 4);
  return u;
}
static uint64_t timestamp(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t)) {
    exit(2);
  }
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static double measure(int single, int host, int seeded) {
  df = host ? modf : gmath_modf;
  ff = host ? modff : gmath_modff;
  if (feclearexcept(FE_ALL_EXCEPT) ||
      feraiseexcept(seeded ? FE_UNDERFLOW | FE_INEXACT : 0)) {
    exit(2);
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = seeded ? 731 : 0;
  uint64_t h = 0, start = timestamp();
  for (int i = 0; i < N; i++) {
    if (single) {
      float whole;
      float part = ff(fx[i], &whole);
      h += fbits(part);
      h ^= fbits(whole);
    } else {
      double whole;
      double part = df(dx[i], &whole);
      h += dbits(part);
      h ^= dbits(whole);
    }
  }
  uint64_t elapsed = timestamp() - start;
  if (fetestexcept(FE_ALL_EXCEPT) != incoming || errno != (seeded ? 731 : 0) ||
      fegetround() != FE_TONEAREST) {
    exit(2);
  }
  sink = h;
  return (double)elapsed / N;
}
static int compare(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
int main(void) {
  if (fesetenv(FE_DFL_ENV) || fesetround(FE_TONEAREST)) {
    return 2;
  }
  printf("compiler %s; C%ld; binary64/binary32; nearest; integer timestamps\n",
         __VERSION__, (long)__STDC_VERSION__);
  uint64_t rng = UINT64_C(0x7369676e65647061);
  const char * names[] = {"mixed-fraction", "below-one", "integral",
                          "subnormal", "wide"};
  puts("401 alternating pairs of4096 same inputs; integer timestamps, "
       "clean/preseeded UF/IX and errno; median ns/call and paired ratio "
       "p10/median/p90; "
       "call/loop/checksum overhead included");
  for (int range = 0; range < 5; range++) {
    for (int j = 0; j < N; j++) {
      uint64_t r = random_word(&rng), d;
      uint32_t f;
      if (range == 0) {
        d = (r & UINT64_C(0x800fffffffffffff)) | ((1023 + r % 20) << 52);
        f = ((uint32_t)r & 0x807fffffu) | ((127u + (uint32_t)(r % 12)) << 23);
      } else if (range == 1) {
        d = (r & UINT64_C(0x800fffffffffffff)) | (UINT64_C(1022) << 52);
        f = ((uint32_t)r & 0x807fffffu) | (126u << 23);
      } else if (range == 2) {
        d = (r & UINT64_C(0x800fffffffffffff)) | (UINT64_C(1075) << 52);
        f = ((uint32_t)r & 0x807fffffu) | (150u << 23);
      } else if (range == 3) {
        d = (r & UINT64_C(0x800fffffffffffff)) | 1;
        f = ((uint32_t)r & 0x807fffffu) | 1;
      } else {
        d = (r & UINT64_C(0x800fffffffffffff)) | ((1 + r % 2046) << 52);
        f = ((uint32_t)r & 0x807fffffu) | ((1u + (uint32_t)(r % 254)) << 23);
      }
      memcpy(&dx[j], &d, 8);
      memcpy(&fx[j], &f, 4);
    }
    for (int j = 0; j < N; j++) {
      double a, b;
      float c, d;
      double (*volatile hd)(double, double *) = modf;
      float (*volatile hf)(float, float *) = modff;
      if (dbits(gmath_modf(dx[j], &a)) != dbits(hd(dx[j], &b)) ||
          dbits(a) != dbits(b) ||
          fbits(gmath_modff(fx[j], &c)) != fbits(hf(fx[j], &d)) ||
          fbits(c) != fbits(d)) {
        fputs("split benchmark value guard failed\n", stderr);
        return 2;
      }
    }
    for (int single = 0; single < 2; single++) {
      for (int seeded = 0; seeded < 2; seeded++) {
        double own[PAIRS], host[PAIRS], ratio[PAIRS];
        for (int p = 0; p < PAIRS; p++) {
          if (p & 1) {
            host[p] = measure(single, 1, seeded);
            own[p] = measure(single, 0, seeded);
          } else {
            own[p] = measure(single, 0, seeded);
            host[p] = measure(single, 1, seeded);
          }
          if (own[p] <= 0 || host[p] <= 0) {
            return 2;
          }
          ratio[p] = own[p] / host[p];
        }
        qsort(own, PAIRS, sizeof(double), compare);
        qsort(host, PAIRS, sizeof(double), compare);
        qsort(ratio, PAIRS, sizeof(double), compare);
        printf("%s %s %s gmath %.3f host %.3f ratio %.3f %.3f %.3f\n",
               single ? "modff" : "modf", names[range],
               seeded ? "UF/IX" : "clean", own[PAIRS / 2], host[PAIRS / 2],
               ratio[PAIRS / 10], ratio[PAIRS / 2], ratio[9 * PAIRS / 10]);
      }
    }
  }
  return 0;
}
