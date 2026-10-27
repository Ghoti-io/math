/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and alternating paired timings.
 * Each number includes call/loop overhead; it is not an application speedup.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/basic.h>
#include <fenv.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 4096
static float xs[N], ys[N];
static volatile double sink;
static uint64_t state = 0x65787472656d6121ull;
static uint64_t random_word(void) {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return state;
}
static double now(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) {
    perror("clock_gettime");
    exit(2);
  }
  return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}
static double measure(float (*volatile fn)(float)) {
  double sum = 0, start = now();
  for (int i = 0; i < N; ++i) {
    sum += (double)fn(xs[i]);
  }
  double ns = (now() - start) * 1e9 / N;
  sink = sum;
  return ns;
}
static double measure2(float (*volatile fn)(float, float)) {
  double sum = 0, start = now();
  for (int i = 0; i < N; ++i) {
    sum += (double)fn(xs[i], ys[i]);
  }
  double ns = (now() - start) * 1e9 / N;
  sink = sum;
  return ns;
}
static double sample(int api, int host) {
  float (*const ours[])(float) = {gmath_floorf, gmath_ceilf, gmath_truncf,
      gmath_roundf, gmath_rintf, gmath_fabsf, gmath_sqrtf};
  float (*const libm[])(float) = {floorf, ceilf, truncf, roundf, rintf, fabsf, sqrtf};
  if (api == 7) {
    return measure2(host ? copysignf : gmath_copysignf);
  }
  return measure(host ? libm[api] : ours[api]);
}
static int compare(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
static float from32(uint32_t bits) {
  float x;
  memcpy(&x, &bits, sizeof x);
  return x;
}
static void inputs(int range, int positive) {
  for (int i = 0; i < N; ++i) {
    uint32_t a = (uint32_t)random_word();
    uint32_t sign = positive ? 0 : a & 0x80000000u;
    uint32_t b = (uint32_t)random_word();
    ys[i] = from32((b & 0x807fffffu) | ((1u + b % 254) << 23));
    if (range == 0) {
      float magnitude = (float)(a & 0x007fffffu) * 0x1p-13f;
      xs[i] = sign ? -magnitude : magnitude;
    }
    else if (range == 1) {
      float magnitude = (float)(a & 0x007fffffu) * 0x1p-22f;
      xs[i] = sign ? -magnitude : magnitude;
    }
    else if (range == 2) {
      xs[i] = from32(sign | (a & 0x007fffffu) | 1);
    }
    else {
      xs[i] = from32(sign | ((150u + a % 105) << 23) | (a & 0x007fffffu));
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-floatbasic [repeats: 1..100000]\n");
    return 2;
  }
  if (fesetround(FE_TONEAREST) != 0) {
    fputs("cannot select FE_TONEAREST\n", stderr);
    return 2;
  }
  int repeats = (int)requested;
  const char * names[] = {"common signed", "small signed", "subnormal", "large integral"};
  const char * apis[] = {"floorf", "ceilf", "truncf", "roundf", "rintf", "fabsf", "sqrtf", "copysignf"};
  double * ratios = malloc((size_t)repeats * sizeof *ratios);
  if (!ratios) {
    perror("benchmark ratios");
    return 2;
  }
  printf("float basic: %d alternating pairs, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("Times are minima in ns/call; ratios are gmath/libm; pair median uses same-input pairs.");
  puts("FE_TONEAREST selects ties-to-even rintf; sqrtf inputs are positive magnitudes.");
  puts("Results describe each input set and function; they establish no overall speed advantage.");
  puts("range              function    gmath ns    libm ns  min ratio  pair median");
  for (int range = 0; range < 4; ++range) {
    for (int api = 0; api < 8; ++api) {
      inputs(range, api == 6);
      for (int r = 0; r < 10; ++r) {
        (void)sample(api, r & 1);
        (void)sample(api, !(r & 1));
      }
      double best_a = 1e30, best_b = 1e30;
      for (int r = 0; r < repeats; ++r) {
        double a, b;
        if (r & 1) {
          b = sample(api, 1);
          a = sample(api, 0);
        }
        else {
          a = sample(api, 0);
          b = sample(api, 1);
        }
        if (a < best_a) {
          best_a = a;
        }
        if (b < best_b) {
          best_b = b;
        }
        ratios[r] = a / b;
      }
      qsort(ratios, (size_t)repeats, sizeof *ratios, compare);
      double median = ratios[repeats / 2];
      if (repeats % 2 == 0) {
        median = 0.5 * (median + ratios[repeats / 2 - 1]);
      }
      printf("%-18s %-9s %10.1f %10.1f %9.2fx %11.2fx\n", names[range], apis[api],
          best_a, best_b, best_a / best_b, median);
    }
  }
  free(ratios);
  return 0;
}
