/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and alternating paired timings.
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
static double measure(double (*volatile fn)(double)) {
  double sum = 0, start = now();
  for (int i = 0; i < N; ++i) {
    sum += fn(xs[i]);
  }
  double ns = (now() - start) * 1e9 / N;
  sink = sum;
  return ns;
}
static int compare(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
static double from64(uint64_t bits) {
  double x;
  memcpy(&x, &bits, sizeof x);
  return x;
}
static void inputs(int range) {
  for (int i = 0; i < N; ++i) {
    uint64_t a = random_word();
    uint64_t sign = a & 0x8000000000000000ull;
    double u = (double)(a >> 11) * 0x1p-53;
    if (range == 0) {
      xs[i] = (a & 1 ? -1 : 1) * (1 + 7 * u);
    }
    else if (range == 1) {
      xs[i] = from64(sign | ((1 + a % 2046) << 52) | (a & 0x000fffffffffffffull));
    }
    else if (range == 2) {
      xs[i] = from64(sign | (a & 0x000fffffffffffffull) | 1);
    }
    else if (range == 3) {
      int e = 3 * ((int)(a % 700) - 358);
      uint64_t magnitude = e < -1022 ? 1ull << (unsigned)(e + 1074) :
          (uint64_t)(e + 1023) << 52;
      xs[i] = from64(sign | magnitude);
    }
    else {
      uint64_t n = 1 + a % 1000;
      double cube = (double)(n * n * n);
      uint64_t bits;
      memcpy(&bits, &cube, sizeof bits);
      bits += (a >> 12) % 3;
      bits -= 1;
      xs[i] = from64(sign | bits);
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-cbrt [repeats: 1..100000]\n");
    return 2;
  }
  int repeats = (int)requested;
  const char * names[] = {"signed [1,8]", "wide signed exponents", "subnormal arguments",
      "exact binary cubes", "integer cube neighbors"};
  double * ratios = malloc((size_t)repeats * sizeof *ratios);
  if (!ratios) {
    perror("benchmark ratios");
    return 2;
  }
  printf("cbrt: %d alternating pairs, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("Times are minima in ns/call; ratios are gmath/libm; pair median uses same-input pairs.");
  puts("range                     gmath ns    libm ns  min ratio  pair median");
  for (int range = 0; range < 5; ++range) {
    inputs(range);
    for (int r = 0; r < 10; ++r) {
      if (r & 1) {
        (void)measure(cbrt);
        (void)measure(gmath_cbrt);
      }
      else {
        (void)measure(gmath_cbrt);
        (void)measure(cbrt);
      }
    }
    double best_a = 1e30, best_b = 1e30;
    for (int r = 0; r < repeats; ++r) {
      double a, b;
      if (r & 1) {
        b = measure(cbrt);
        a = measure(gmath_cbrt);
      }
      else {
        a = measure(gmath_cbrt);
        b = measure(cbrt);
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
    printf("%-24s %10.1f %10.1f %9.2fx %11.2fx\n", names[range],
        best_a, best_b, best_a / best_b, median);
  }
  free(ratios);
  return 0;
}
