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
#if defined(GMATH_LOGB_BASELINE) != defined(GMATH_LOGBF_BASELINE)
#error "Configure both exponent baseline functions together"
#endif
#ifdef GMATH_LOGB_BASELINE
#ifndef GMATH_EXPONENT_BASELINE_IDENTITY
#error "Exponent baseline identity is required"
#endif
extern double GMATH_LOGB_BASELINE(double);
extern float GMATH_LOGBF_BASELINE(float);
#define EXPONENT_BASELINE_D GMATH_LOGB_BASELINE
#define EXPONENT_BASELINE_F GMATH_LOGBF_BASELINE
#define EXPONENT_BASELINE_LABEL "prior"
#define EXPONENT_BASELINE_ERRNO 1
#else
#define EXPONENT_BASELINE_D logb
#define EXPONENT_BASELINE_F logbf
#define EXPONENT_BASELINE_LABEL "host"
#define EXPONENT_BASELINE_ERRNO 0
#endif
#define N 4096
#define PAIRS 401
static double dx[N];
static float fx[N];
static double (*volatile df)(double);
static float (*volatile ff)(float);
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
static double measure(int single, int host, int seeded, int range) {
  df = host ? EXPONENT_BASELINE_D : gmath_logb;
  ff = host ? EXPONENT_BASELINE_F : gmath_logbf;
  if (feclearexcept(FE_ALL_EXCEPT) ||
      feraiseexcept(seeded ? FE_UNDERFLOW | FE_INEXACT : 0)) {
    exit(2);
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = seeded ? 731 : 0;
  uint64_t h = 0, start = timestamp();
  for (int i = 0; i < N; i++) {
    if (single) {
      h += fbits(ff(fx[i]));
    } else {
      h += dbits(df(dx[i]));
    }
  }
  uint64_t elapsed = timestamp() - start;
  int expected = incoming | (range == 5   ? FE_DIVBYZERO
                             : range == 8 ? FE_INVALID
                                          : 0);
  if (fetestexcept(FE_ALL_EXCEPT) != expected ||
      ((!host || EXPONENT_BASELINE_ERRNO || range < 5) &&
       errno != (seeded ? 731 : 0)) ||
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
#ifdef GMATH_LOGB_BASELINE
  double (*volatile current_d)(double) = gmath_logb;
  float (*volatile current_f)(float) = gmath_logbf;
  double (*volatile prior_d)(double) = GMATH_LOGB_BASELINE;
  float (*volatile prior_f)(float) = GMATH_LOGBF_BASELINE;
  if (current_d == prior_d || current_f == prior_f) {
    fputs("exponent baseline aliases current function\n", stderr);
    return 2;
  }
  fputs(GMATH_EXPONENT_BASELINE_IDENTITY, stdout);
#endif
  uint64_t rng = UINT64_C(0x7369676e65647061);
  const char * names[] = {"normal",   "subnormal", "binary-powers",
                          "near-one", "wide",      "zero",
                          "infinity", "quiet-NaN", "signaling-NaN"};
  puts("8 paired warmups;401 alternating pairs of4096 same inputs; integer "
       "timestamps, "
       "clean/preseeded UF/IX and errno; median ns/call and paired ratio "
       "p10/median/p90; "
       "call/loop/checksum overhead/first-exception amortization included; "
       "host exceptional errno and NaN payloads may differ");
  for (int range = 0; range < 9; range++) {
    for (int j = 0; j < N; j++) {
      uint64_t r = random_word(&rng), d;
      uint32_t f;
      if (range == 0) {
        d = (r & UINT64_C(0x800fffffffffffff)) | ((1023 + r % 20) << 52);
        f = ((uint32_t)r & 0x807fffffu) | ((127u + (uint32_t)(r % 12)) << 23);
      } else if (range == 1) {
        d = (r & UINT64_C(0x800fffffffffffff)) | 1;
        f = ((uint32_t)r & 0x807fffffu) | 1;
      } else if (range == 2) {
        d = (r & UINT64_C(0x8000000000000000)) | ((1 + r % 2046) << 52);
        f = ((uint32_t)r & 0x80000000u) | ((1u + (uint32_t)(r % 254)) << 23);
      } else if (range == 3) {
        d = (r & UINT64_C(0x8000000000000000)) |
            (UINT64_C(0x3ff0000000000000) + (r % 5) - 2);
        f = ((uint32_t)r & 0x80000000u) |
            (0x3f800000u + (uint32_t)(r % 5) - 2u);
      } else if (range == 5) {
        d = r & UINT64_C(0x8000000000000000);
        f = (uint32_t)r & 0x80000000u;
      } else if (range == 6) {
        d = (r & UINT64_C(0x8000000000000000)) | UINT64_C(0x7ff0000000000000);
        f = ((uint32_t)r & 0x80000000u) | 0x7f800000u;
      } else if (range >= 7) {
        d = (r & UINT64_C(0x8007ffffffffffff)) | UINT64_C(0x7ff0000000000001);
        f = ((uint32_t)r & 0x803fffffu) | 0x7f800001u;
        if (range == 7) {
          d |= UINT64_C(0x0008000000000000);
          f |= 0x00400000u;
        }
      } else {
        d = (r & UINT64_C(0x800fffffffffffff)) | ((1 + r % 2046) << 52);
        f = ((uint32_t)r & 0x807fffffu) | ((1u + (uint32_t)(r % 254)) << 23);
      }
      memcpy(&dx[j], &d, 8);
      memcpy(&fx[j], &f, 4);
    }
    for (int j = 0; j < N; j++) {
      double (*volatile hd)(double) = EXPONENT_BASELINE_D;
      float (*volatile hf)(float) = EXPONENT_BASELINE_F;
      uint64_t own_d = dbits(gmath_logb(dx[j])), host_d = dbits(hd(dx[j]));
      uint32_t own_f = fbits(gmath_logbf(fx[j])), host_f = fbits(hf(fx[j]));
#ifdef GMATH_LOGB_BASELINE
      int valid = own_d == host_d && own_f == host_f;
#else
      int valid = range >= 7 ? (own_d == UINT64_C(0x7ff8000000000000) &&
                                (host_d & UINT64_C(0x7fffffffffffffff)) >
                                    UINT64_C(0x7ff0000000000000) &&
                                own_f == 0x7fc00000u &&
                                (host_f & 0x7fffffffu) > 0x7f800000u)
                             : (own_d == host_d && own_f == host_f);
#endif
      if (!valid) {
        fputs("exponent benchmark bit/class guard failed\n", stderr);
        return 2;
      }
    }
    for (int single = 0; single < 2; single++) {
      for (int seeded = 0; seeded < 2; seeded++) {
        for (int warm = 0; warm < 8; warm++) {
          if (warm & 1) {
            (void)measure(single, 1, seeded, range);
            (void)measure(single, 0, seeded, range);
          } else {
            (void)measure(single, 0, seeded, range);
            (void)measure(single, 1, seeded, range);
          }
        }
        double own[PAIRS], host[PAIRS], ratio[PAIRS];
        for (int p = 0; p < PAIRS; p++) {
          if (p & 1) {
            host[p] = measure(single, 1, seeded, range);
            own[p] = measure(single, 0, seeded, range);
          } else {
            own[p] = measure(single, 0, seeded, range);
            host[p] = measure(single, 1, seeded, range);
          }
          if (own[p] <= 0 || host[p] <= 0) {
            return 2;
          }
          ratio[p] = own[p] / host[p];
        }
        qsort(own, PAIRS, sizeof(double), compare);
        qsort(host, PAIRS, sizeof(double), compare);
        qsort(ratio, PAIRS, sizeof(double), compare);
        printf("%s %s %s gmath %.3f %s %.3f ratio %.3f %.3f %.3f\n",
               single ? "logbf" : "logb", names[range],
               seeded ? "UF/IX" : "clean", own[PAIRS / 2],
               EXPONENT_BASELINE_LABEL, host[PAIRS / 2], ratio[PAIRS / 10],
               ratio[PAIRS / 2], ratio[9 * PAIRS / 10]);
      }
    }
  }
  return 0;
}
