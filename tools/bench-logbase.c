/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and best-of-repeat timings.
 * Each number includes call/loop overhead; it is not an application speedup.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/elementary.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 4096
static double xs[N];
static float xf[N];
static volatile double sink;
static uint64_t state = 0x65787472656d6121ull;
static uint64_t random_word(void) {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return state;
}
static double from64(uint64_t bits) {
  double x;
  memcpy(&x, &bits, sizeof x);
  return x;
}
static float from32(uint32_t bits) {
  float x;
  memcpy(&x, &bits, sizeof x);
  return x;
}
static double now(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) {
    perror("clock_gettime");
    exit(2);
  }
  return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}
static double measure(double (*volatile fn)(double), int repeats) {
  double best = 1e30;
  for (int r = 0; r < repeats; ++r) {
    double sum = 0, start = now();
    for (int i = 0; i < N; ++i) {
      sum += fn(xs[i]);
    }
    double ns = (now() - start) * 1e9 / N;
    sink = sum;
    if (ns < best) {
      best = ns;
    }
  }
  return best;
}
static double measuref(float (*volatile fn)(float), int repeats) {
  double best = 1e30;
  for (int r = 0; r < repeats; ++r) {
    double sum = 0, start = now();
    for (int i = 0; i < N; ++i) {
      sum += (double)fn(xf[i]);
    }
    double ns = (now() - start) * 1e9 / N;
    sink = sum;
    if (ns < best) {
      best = ns;
    }
  }
  return best;
}
static void inputs(int range) {
  for (int i = 0; i < N; ++i) {
    uint64_t a = random_word();
    if (range == 0) {
      xs[i] = (double)(1 + a % 8000000) * 0x1p-13;
      xf[i] = (float)xs[i];
    }
    else if (range == 1) {
      xs[i] = from64(((1 + a % 2046) << 52) | (a & 0x000fffffffffffffull));
      xf[i] = from32(((1u + (uint32_t)(a % 254)) << 23) | ((uint32_t)a & 0x007fffffu));
    }
    else if (range == 2) {
      xs[i] = from64(0x3ff0000000000000ull + a % 4097 - 2048);
      xf[i] = from32(0x3f800000u + (uint32_t)(a % 4097) - 2048u);
    }
    else if (range == 3) {
      xs[i] = from64((a & 0x000fffffffffffffull) | 1);
      xf[i] = from32(((uint32_t)a & 0x007fffffu) | 1);
    }
    else if (range == 4) {
      int e = (int)(a % 2098) - 1074;
      int ef = (int)(a % 277) - 149;
      xs[i] = from64(e < -1022 ? 1ull << (unsigned)(e + 1074) :
          (uint64_t)(e + 1023) << 52);
      xf[i] = from32(ef < -126 ? 1u << (unsigned)(ef + 149) :
          (uint32_t)(ef + 127) << 23);
    }
    else {
      /* 10^0..10^22 and 10^0..10^10 are exactly representable. */
      xs[i] = 1;
      xf[i] = 1;
      for (unsigned n = 0; n < a % 23; ++n) {
        xs[i] *= 10;
      }
      for (unsigned n = 0; n < a % 11; ++n) {
        xf[i] *= 10;
      }
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-logbase [repeats: 1..100000]\n");
    return 2;
  }
  int repeats = (int)requested;
  double (*ours[])(double) = {gmath_log2, gmath_log10};
  double (*host[])(double) = {log2, log10};
  const char * names[] = {"common positive", "wide positive", "near one",
      "subnormal operands", "exact binary powers", "exact decimal powers"};
  printf("logarithm bases: best of %d repeats, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("range                  function    gmath ns    libm ns    ratio");
  for (int range = 0; range < 6; ++range) {
    inputs(range);
    for (int base = 0; base < 2; ++base) {
      (void)measure(ours[base], 10);
      (void)measure(host[base], 10);
      double a = measure(ours[base], repeats);
      double b = measure(host[base], repeats);
      printf("%-22s %-8s %10.1f %10.1f %8.2fx\n", names[range], base ? "log10" : "log2", a, b, a / b);
    }
    (void)measuref(gmath_log2f, 10);
    (void)measuref(log2f, 10);
    double a = measuref(gmath_log2f, repeats);
    double b = measuref(log2f, repeats);
    printf("%-22s %-8s %10.1f %10.1f %8.2fx\n", names[range], "log2f", a, b, a / b);
  }
  return 0;
}
