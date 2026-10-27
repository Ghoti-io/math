/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and best-of-repeat timings.
 * Each number includes call/loop overhead; it is not an application speedup.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/basic.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 4096
static double xs[N], ys[N];
static float xf[N], yf[N];
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
static double measure(double (*volatile fn)(double, double), int repeats) {
  double best = 1e30;
  for (int r = 0; r < repeats; ++r) {
    double sum = 0, start = now();
    for (int i = 0; i < N; ++i) {
      sum += fn(xs[i], ys[i]);
    }
    double ns = (now() - start) * 1e9 / N;
    sink = sum;
    if (ns < best) {
      best = ns;
    }
  }
  return best;
}
static double measuref(float (*volatile fn)(float, float), int repeats) {
  double best = 1e30;
  for (int r = 0; r < repeats; ++r) {
    double sum = 0, start = now();
    for (int i = 0; i < N; ++i) {
      sum += (double)fn(xf[i], yf[i]);
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
    uint64_t a = random_word(), b = random_word();
    uint64_t sa = a & 0x8000000000000000ull;
    uint64_t sb = b & 0x8000000000000000ull;
    uint32_t sfa = (uint32_t)(a >> 32) & 0x80000000u;
    uint32_t sfb = (uint32_t)(b >> 32) & 0x80000000u;
    xs[i] = from64(sa | ((1000 + a % 41) << 52) | (a & 0x000fffffffffffffull));
    ys[i] = from64(sb | ((1000 + b % 41) << 52) | (b & 0x000fffffffffffffull));
    xf[i] = from32(sfa | ((110u + (uint32_t)(a % 31)) << 23) | ((uint32_t)a & 0x007fffffu));
    yf[i] = from32(sfb | ((110u + (uint32_t)(b % 31)) << 23) | ((uint32_t)b & 0x007fffffu));
    if (range == 1) {
      xs[i] = from64(sa | (a & 0x000fffffffffffffull) | 1);
      ys[i] = from64(sb | (b & 0x000fffffffffffffull) | 1);
      xf[i] = from32(sfa | ((uint32_t)a & 0x007fffffu) | 1);
      yf[i] = from32(sfb | ((uint32_t)b & 0x007fffffu) | 1);
    }
    else if (range == 2) {
      xs[i] = from64(i & 1 ? 0x8000000000000000ull : 0);
      ys[i] = from64(i & 2 ? 0x8000000000000000ull : 0);
      xf[i] = from32(i & 1 ? 0x80000000u : 0);
      yf[i] = from32(i & 2 ? 0x80000000u : 0);
    }
    else if (range == 3) {
      if (i % 3 != 0) {
        xs[i] = from64(sa | 0x7ff0000000000000ull);
        xf[i] = from32(sfa | 0x7f800000u);
      }
      if (i % 3 != 1) {
        ys[i] = from64(sb | 0x7ff0000000000000ull);
        yf[i] = from32(sfb | 0x7f800000u);
      }
    }
    else if (range == 4) {
      if (i % 3 != 0) {
        xs[i] = from64(sa | 0x7ff8000000000001ull);
        xf[i] = from32(sfa | 0x7fc00001u);
      }
      if (i % 3 != 1) {
        ys[i] = from64(sb | 0x7ff8000000000007ull);
        yf[i] = from32(sfb | 0x7fc00007u);
      }
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-extrema [repeats: 1..100000]\n");
    return 2;
  }
  int repeats = (int)requested;
  double (*ours[])(double, double) = {gmath_fmin, gmath_fmax};
  double (*host[])(double, double) = {fmin, fmax};
  float (*oursf[])(float, float) = {gmath_fminf, gmath_fmaxf};
  float (*hostf[])(float, float) = {fminf, fmaxf};
  const char * names[] = {"finite random signs", "subnormal operands", "zero ties", "infinities", "quiet NaN mix"};
  printf("extrema: best of %d repeats, %d pairs; indirect calls include loop overhead\n", repeats, N);
  puts("Host libm may choose different signed-zero ties; these rows measure timing only.");
  puts("range                  function    gmath ns    libm ns    ratio");
  for (int range = 0; range < 5; ++range) {
    inputs(range);
    for (int maximum = 0; maximum < 2; ++maximum) {
      (void)measure(ours[maximum], 10);
      (void)measure(host[maximum], 10);
      double a = measure(ours[maximum], repeats);
      double b = measure(host[maximum], repeats);
      printf("%-22s %-8s %10.1f %10.1f %8.2fx\n", names[range], maximum ? "fmax" : "fmin", a, b, a / b);
      (void)measuref(oursf[maximum], 10);
      (void)measuref(hostf[maximum], 10);
      a = measuref(oursf[maximum], repeats);
      b = measuref(hostf[maximum], repeats);
      printf("%-22s %-8s %10.1f %10.1f %8.2fx\n", names[range], maximum ? "fmaxf" : "fminf", a, b, a / b);
    }
  }
  return 0;
}
