/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and alternating paired timings.
 * Each number includes call/loop overhead; it is not an application speedup.
 */
#define _POSIX_C_SOURCE 200809L
#include <ghoti.io/math/elementary.h>
#include <fenv.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 4096
static float xs[N];
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
static double sample(int api, int host) {
  float (*const ours[])(float) = {gmath_sinf, gmath_cosf, gmath_tanf};
  float (*const libm[])(float) = {sinf, cosf, tanf};
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
static void inputs(int range) {
  for (int i = 0; i < N; ++i) {
    uint32_t a = (uint32_t)random_word();
    uint32_t sign = a & 0x80000000u;
    if (range < 2) {
      float magnitude = (float)(a & 0x007fffffu) * 0x1p-23f;
      if (range == 1) {
        magnitude *= 10;
      }
      xs[i] = sign ? -magnitude : magnitude;
    }
    else if (range == 2) {
      xs[i] = from32(sign | ((128u + a % 20) << 23) | (a & 0x007fffffu));
    }
    else if (range == 3) {
      xs[i] = from32(sign | ((148u + a % 107) << 23) | (a & 0x007fffffu));
    }
    else {
      xs[i] = from32(sign | (a & 0x007fffffu) | 1);
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-floattrig [repeats: 1..100000]\n");
    return 2;
  }
  if (fesetenv(FE_DFL_ENV) != 0 || fesetround(FE_TONEAREST) != 0) {
    fputs("cannot select the default environment and FE_TONEAREST\n", stderr);
    return 2;
  }
  int repeats = (int)requested;
  const char * names[] = {"signed [-1,1]", "signed [-10,10]", "moderate exponents",
      "large exponents", "subnormal inputs"};
  const char * apis[] = {"sinf", "cosf", "tanf"};
  double * ratios = malloc((size_t)repeats * sizeof *ratios);
  if (!ratios) {
    perror("benchmark ratios");
    return 2;
  }
  printf("float trig: %d alternating pairs, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("Times are minima in ns/call; ratios are gmath/libm; pair median uses same-input pairs.");
  puts("Default floating environment, FE_TONEAREST; identical fixed inputs in each pair.");
  puts("Results describe each input set and function; they establish no overall speed advantage.");
  puts("range              function    gmath ns    libm ns  min ratio  pair median");
  for (int range = 0; range < 5; ++range) {
    inputs(range);
    for (int api = 0; api < 3; ++api) {
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
