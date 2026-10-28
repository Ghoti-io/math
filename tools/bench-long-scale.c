/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired scalar-call timings; numerical/state checks are outside timing.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <limits.h>
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
static long exponents[N];
static double (*volatile df)(double, long);
static float (*volatile ff)(float, long);
static volatile uint64_t sink;
static uint64_t random_word(uint64_t * word) {
  *word ^= *word << 13;
  *word ^= *word >> 7;
  *word ^= *word << 17;
  return *word;
}
static uint64_t dbits(double x) {
  uint64_t word;
  memcpy(&word, &x, 8);
  return word;
}
static uint32_t fbits(float x) {
  uint32_t word;
  memcpy(&word, &x, 4);
  return word;
}
static uint64_t timestamp(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t)) {
    perror("clock_gettime");
    exit(2);
  }
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static int expected_flags(int single, int range) {
  if (range == 3 || range == 7) {
    return FE_UNDERFLOW | FE_INEXACT;
  }
  if (range == 4) {
    return FE_INEXACT | (single ? 0 : FE_UNDERFLOW);
  }
  if (range == 5 || range == 6) {
    return FE_OVERFLOW | FE_INEXACT;
  }
  if (range == 10) {
    return FE_INVALID;
  }
  return 0;
}
static uint64_t measure(int single, int host, int seeded, int range) {
  df = host ? scalbln : gmath_scalbln;
  ff = host ? scalblnf : gmath_scalblnf;
  if (feclearexcept(FE_ALL_EXCEPT) ||
      feraiseexcept(seeded ? FE_UNDERFLOW | FE_INEXACT : 0)) {
    exit(2);
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = seeded ? 731 : 0;
  uint64_t sum = 0, start = timestamp();
  if (single) {
    for (int j = 0; j < N; j++) {
      sum ^= fbits(ff(fx[j], exponents[j]));
    }
  } else {
    for (int j = 0; j < N; j++) {
      sum ^= dbits(df(dx[j], exponents[j]));
    }
  }
  uint64_t end = timestamp();
  int flags = fetestexcept(FE_ALL_EXCEPT), error = errno, mode = fegetround();
  if (mode != FE_TONEAREST || (flags & incoming) != incoming ||
      (!host && (flags != (incoming | expected_flags(single, range)) ||
                 error != (seeded ? 731 : 0)))) {
    fprintf(stderr,
            "long scale benchmark state guard failed type%d host%d range%d "
            "flags%x incoming%x errno%d\n",
            single, host, range, flags, incoming, error);
    exit(2);
  }
  sink ^= sum;
  return end - start;
}
static int compare_u64(const void * a, const void * b) {
  uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return (x > y) - (x < y);
}
static int compare_double(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
int main(void) {
  if (fesetround(FE_TONEAREST)) {
    return 2;
  }
  printf("compiler %s; C%ld; native long%u; nearest; integer timestamps\n",
         __VERSION__, (long)__STDC_VERSION__,
         (unsigned)(sizeof(long) * CHAR_BIT));
  puts("8 paired warmups;401 alternating pairs of4096 same inputs; "
       "clean/preseeded UF/IX and errno; median ns/call and paired ratio "
       "p10/median/p90; call/loop/checksum/timestamp and first-exception "
       "amortization included; host new flags, exceptional errno and NaN "
       "payloads may differ");
  const char * names[] = {"normal",
                          "subnormal-input",
                          "exact-subnormal-result",
                          "inexact-subnormal-result",
                          "rounded-normal",
                          "overflow",
                          "long-max",
                          "long-min",
                          "zero-infinity",
                          "quiet-NaN",
                          "signaling-NaN"};
  uint64_t rng = UINT64_C(0x6e61746976656c6f);
  enum { RANGES = sizeof names / sizeof *names };
  for (int range = 0; range < RANGES; range++) {
    for (int j = 0; j < N; j++) {
      uint64_t r = random_word(&rng), sign = r & UINT64_C(0x8000000000000000),
               d;
      uint32_t fs = (uint32_t)r & 0x80000000u, f;
      long n;
      switch (range) {
      case 0:
        d = sign | ((1003 + (r % 40)) << 52) |
            (r & UINT64_C(0x000fffffffffffff));
        f = fs | ((107u + (uint32_t)(r % 40)) << 23) |
            ((uint32_t)r & 0x7fffffu);
        n = (long)(r % 33) - 16;
        break;
      case 1:
        d = sign | (r & UINT64_C(0x000fffffffffffff)) | 1;
        f = fs | ((uint32_t)r & 0x7fffffu) | 1;
        n = 1;
        break;
      case 2:
        d = sign | UINT64_C(0x0010000000000000) |
            (r & UINT64_C(0x000ffffffffffffe));
        f = fs | 0x00800000u | ((uint32_t)r & 0x7ffffeu);
        n = -1;
        break;
      case 3:
        d = sign | UINT64_C(0x0010000000000001) |
            (r & UINT64_C(0x0007ffffffffffff));
        f = fs | 0x00800001u | ((uint32_t)r & 0x3fffffu);
        n = -1;
        break;
      case 4:
        d = sign | UINT64_C(0x001fffffffffffff);
        f = fs | 0x00ffffffu;
        n = -1;
        break;
      case 5:
        d = sign | UINT64_C(0x7fefffffffffffff);
        f = fs | 0x7f7fffffu;
        n = 1;
        break;
      case 6:
        d = sign | UINT64_C(0x3ff0000000000000) |
            (r & UINT64_C(0x000fffffffffffff));
        f = fs | 0x3f800000u | ((uint32_t)r & 0x7fffffu);
        n = LONG_MAX;
        break;
      case 7:
        d = sign | UINT64_C(0x3ff0000000000000) |
            (r & UINT64_C(0x000fffffffffffff));
        f = fs | 0x3f800000u | ((uint32_t)r & 0x7fffffu);
        n = LONG_MIN;
        break;
      case 8:
        d = sign | ((j & 1) ? UINT64_C(0x7ff0000000000000) : 0);
        f = fs | ((j & 1) ? 0x7f800000u : 0);
        n = (j & 2) ? LONG_MAX : LONG_MIN;
        break;
      default:
        d = sign | UINT64_C(0x7ff0000000000001) |
            (r & UINT64_C(0x0007ffffffffffff));
        f = fs | 0x7f800001u | ((uint32_t)r & 0x3fffffu);
        if (range == 9) {
          d |= UINT64_C(0x0008000000000000);
          f |= 0x00400000u;
        }
        n = (j & 2) ? LONG_MAX : LONG_MIN;
        break;
      }
      memcpy(&dx[j], &d, 8);
      memcpy(&fx[j], &f, 4);
      exponents[j] = n;
    }
    for (int j = 0; j < N; j++) {
      double (*volatile hd)(double, long) = scalbln;
      float (*volatile hf)(float, long) = scalblnf;
      uint64_t own_d = dbits(gmath_scalbln(dx[j], exponents[j])),
               host_d = dbits(hd(dx[j], exponents[j]));
      uint32_t own_f = fbits(gmath_scalblnf(fx[j], exponents[j])),
               host_f = fbits(hf(fx[j], exponents[j]));
      int valid = range >= 9 ? own_d == UINT64_C(0x7ff8000000000000) &&
                                   (host_d & UINT64_C(0x7fffffffffffffff)) >
                                       UINT64_C(0x7ff0000000000000) &&
                                   own_f == 0x7fc00000u &&
                                   (host_f & 0x7fffffffu) > 0x7f800000u
                             : own_d == host_d && own_f == host_f;
      if (!valid) {
        fputs("long scale benchmark bit/class guard failed\n", stderr);
        return 2;
      }
    }
    for (int single = 0; single < 2; single++) {
      for (int seeded = 0; seeded < 2; seeded++) {
        for (int warm = 0; warm < 8; warm++) {
          (void)measure(single, warm & 1, seeded, range);
          (void)measure(single, !(warm & 1), seeded, range);
        }
        uint64_t own[PAIRS], host[PAIRS];
        double ratio[PAIRS];
        for (int pair = 0; pair < PAIRS; pair++) {
          if (pair & 1) {
            host[pair] = measure(single, 1, seeded, range);
            own[pair] = measure(single, 0, seeded, range);
          } else {
            own[pair] = measure(single, 0, seeded, range);
            host[pair] = measure(single, 1, seeded, range);
          }
          if (!host[pair]) {
            return 2;
          }
          ratio[pair] = (double)own[pair] / (double)host[pair];
        }
        qsort(own, PAIRS, sizeof *own, compare_u64);
        qsort(host, PAIRS, sizeof *host, compare_u64);
        qsort(ratio, PAIRS, sizeof *ratio, compare_double);
        printf("%s %s %s gmath %.3f host %.3f ratio %.3f %.3f %.3f\n",
               single ? "scalblnf" : "scalbln", names[range],
               seeded ? "UF/IX" : "clean", (double)own[PAIRS / 2] / N,
               (double)host[PAIRS / 2] / N, ratio[PAIRS / 10], ratio[PAIRS / 2],
               ratio[(PAIRS * 9) / 10]);
      }
    }
  }
  return sink == UINT64_C(0xdeadbeef) ? 1 : 0;
}
