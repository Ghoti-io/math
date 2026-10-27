/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Paired same-input indirect calls, with state checks outside timed regions.
 */
#define _POSIX_C_SOURCE 200809L
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
static float input[N];
static int exponent[N];
static volatile uint32_t sink;
static uint32_t random_state = 0x7363616cu;
static uint32_t random_word(void) {
  random_state ^= random_state << 13;
  random_state ^= random_state >> 17;
  random_state ^= random_state << 5;
  return random_state;
}
static float value(uint32_t b) {
  float x;
  memcpy(&x, &b, 4);
  return x;
}
static uint32_t bits(float x) {
  uint32_t b;
  memcpy(&b, &x, 4);
  return b;
}
static float (*volatile scale_fn)(float, int);
static float (*volatile fraction_fn)(float, int *);
static int (*volatile exponent_fn)(float);
static double measure(int kind, int host, int seeded) {
  scale_fn = host ? (kind == 0 ? scalbnf : ldexpf)
                  : (kind == 0 ? gmath_scalbnf : gmath_ldexpf);
  fraction_fn = host ? frexpf : gmath_frexpf;
  exponent_fn = host ? ilogbf : gmath_ilogbf;
  if (feclearexcept(FE_ALL_EXCEPT) ||
      (seeded && feraiseexcept(FE_UNDERFLOW | FE_INEXACT))) {
    exit(2);
  }
  if (fetestexcept(FE_ALL_EXCEPT) !=
      (seeded ? (FE_UNDERFLOW | FE_INEXACT) : 0)) {
    exit(2);
  }
  struct timespec a, b;
  uint32_t sum = 0;
  if (clock_gettime(CLOCK_MONOTONIC, &a)) {
    exit(2);
  }
  if (kind < 2) {
    for (int i = 0; i < N; ++i) {
      sum += bits(scale_fn(input[i], exponent[i]));
    }
  } else if (kind == 2) {
    for (int i = 0; i < N; ++i) {
      int e;
      sum += bits(fraction_fn(input[i], &e)) + (uint32_t)e;
    }
  } else {
    for (int i = 0; i < N; ++i) {
      sum += (uint32_t)exponent_fn(input[i]);
    }
  }
  if (clock_gettime(CLOCK_MONOTONIC, &b)) {
    exit(2);
  }
  if (fegetround() != FE_TONEAREST ||
      (seeded && (fetestexcept(FE_UNDERFLOW | FE_INEXACT) !=
                  (FE_UNDERFLOW | FE_INEXACT)))) {
    exit(2);
  }
  sink = sum;
  return ((double)(b.tv_sec - a.tv_sec) * 1e9 +
          (double)(b.tv_nsec - a.tv_nsec)) /
         N;
}
static int compare(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
static void verify(void) {
  for (int i = 0; i < N; ++i) {
    int a, b;
    float (*volatile host_scale)(float, int) = scalbnf;
    float (*volatile host_ldexp)(float, int) = ldexpf;
    float (*volatile host_fraction)(float, int *) = frexpf;
    int (*volatile host_exponent)(float) = ilogbf;
    if (bits(gmath_scalbnf(input[i], exponent[i])) !=
            bits(host_scale(input[i], exponent[i])) ||
        bits(gmath_ldexpf(input[i], exponent[i])) !=
            bits(host_ldexp(input[i], exponent[i])) ||
        bits(gmath_frexpf(input[i], &a)) != bits(host_fraction(input[i], &b)) ||
        a != b || gmath_ilogbf(input[i]) != host_exponent(input[i])) {
      fputs("benchmark value guard failed\n", stderr);
      exit(2);
    }
  }
}
int main(void) {
  if (fesetenv(FE_DFL_ENV) || fesetround(FE_TONEAREST)) {
    return 2;
  }
  const char * names[] = {"normal exact", "subnormal inputs", "tiny rounded",
                          "rounded minimum normal", "overflow"};
  const char * functions[] = {"scalbnf", "ldexpf", "frexpf", "ilogbf"};
  puts("401 alternating pairs of 4096 identical inputs; median ns/call and "
       "paired gmath/libm ratio p10/median/p90; call/loop/checksum/timestamp "
       "overhead included");
  for (int range = 0; range < 5; ++range) {
    for (int i = 0; i < N; ++i) {
      uint32_t r = random_word(), raw;
      if (range == 0) {
        raw = (r & 0x807fffffu) | ((100u + r % 50u) << 23);
        exponent[i] = (int)(r % 41u) - 20;
      } else if (range == 1) {
        raw = (r & 0x807fffffu) | 1u;
        exponent[i] = 20;
      } else if (range == 2) {
        raw = (r & 0x807fffffu) | 0x00800000u;
        exponent[i] = -(int)(1 + r % 26u);
      } else if (range == 3) {
        raw = (r & 0x80000000u) | 0x00ffffffu;
        exponent[i] = -1;
      } else {
        raw = (r & 0x807fffffu) | 0x7f000000u;
        exponent[i] = 8;
      }
      input[i] = value(raw);
    }
    verify();
    for (int kind = 0; kind < 4; ++kind) {
      for (int seeded = 0; seeded < 2; ++seeded) {
        double own[PAIRS], host[PAIRS], ratios[PAIRS];
        for (int p = 0; p < PAIRS; ++p) {
          if (p & 1) {
            host[p] = measure(kind, 1, seeded);
            own[p] = measure(kind, 0, seeded);
          } else {
            own[p] = measure(kind, 0, seeded);
            host[p] = measure(kind, 1, seeded);
          }
          if (own[p] <= 0 || host[p] <= 0) {
            return 2;
          }
          ratios[p] = own[p] / host[p];
        }
        qsort(own, PAIRS, sizeof(double), compare);
        qsort(host, PAIRS, sizeof(double), compare);
        qsort(ratios, PAIRS, sizeof(double), compare);
        printf("%-7s %-23s %s gmath %.3f host %.3f ratio %.3f %.3f %.3f\n",
               functions[kind], names[range], seeded ? "UF/IX" : "clean",
               own[PAIRS / 2], host[PAIRS / 2], ratios[PAIRS / 10],
               ratios[PAIRS / 2], ratios[9 * PAIRS / 10]);
      }
    }
  }
  return 0;
}
