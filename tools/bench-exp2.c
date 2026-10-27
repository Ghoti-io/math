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
static void inputs(int range) {
  for (int i = 0; i < N; ++i) {
    uint64_t a = random_word();
    double u = (double)(a >> 11) * 0x1p-53;
    switch (range) {
    case 0:
      xs[i] = 20 * u - 10;
      break;
    case 1:
      xs[i] = 2000 * u - 1000;
      break;
    case 2:
      xs[i] = 1023 + u;
      break;
    case 3:
      xs[i] = -1075 + 53 * u;
      break;
    case 4:
      xs[i] = (a & 1 ? -1 : 1) * (0.5 + 0.5 * u) * 0x1p-54;
      break;
    default:
      xs[i] = (double)((int)(a % 2098) - 1074);
      break;
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-exp2 [repeats: 1..100000]\n");
    return 2;
  }
  int repeats = (int)requested;
  const char * names[] = {"common [-10,10]", "wide [-1000,1000]", "near overflow",
      "subnormal results", "tiny signed inputs", "exact integers"};
  printf("exp2: best of %d repeats, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("range                     gmath ns    libm ns    ratio");
  for (int range = 0; range < 6; ++range) {
    inputs(range);
    (void)measure(gmath_exp2, 10);
    (void)measure(exp2, 10);
    double a = measure(gmath_exp2, repeats);
    double b = measure(exp2, repeats);
    printf("%-24s %10.1f %10.1f %8.2fx\n", names[range], a, b, a / b);
  }
  return 0;
}
