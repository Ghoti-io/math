/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Fixed inputs, identical indirect calls, warm-up and alternating paired timings.
 * Each number includes call/loop/checksum overhead; it is not an application speedup.
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
static volatile uint32_t sink;
static uint64_t state = 0x6c6f67662d62656eull;
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
  uint32_t checksum = 0;
  double start = now();
  for (int i = 0; i < N; ++i) {
    float result = fn(xs[i]);
    uint32_t bits;
    memcpy(&bits, &result, sizeof bits);
    checksum += bits;
  }
  double ns = (now() - start) * 1e9 / N;
  sink = checksum;
  return ns;
}
static double sample(int host) {
  return measure(host ? logf : gmath_logf);
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
    float u = (float)(a & 0x007fffffu) * 0x1p-23f;
    switch (range) {
    case 0:
      xs[i] = 0.25f + 3.75f * u;
      break;
    case 1:
      xs[i] = from32(((1u + a % 254u) << 23) | (a & 0x007fffffu));
      break;
    case 2:
      xs[i] = from32(0x3f800000u + a % 8193u - 4096u);
      break;
    case 3:
      xs[i] = from32((a & 0x007fffffu) | 1u);
      break;
    case 4: {
      int exponent = (int)(a % 277u) - 149;
      uint32_t word = exponent < -126 ? 1u << (unsigned)(exponent + 149) :
          (uint32_t)(exponent + 127) << 23;
      xs[i] = from32(word);
      break;
    }
    default: {
      // Project the existing logarithm grid to float and include neighbors.
      unsigned row = a % 129u;
      uint64_t bits = 0x3fe6a00000000000ull + ((uint64_t)row << 45);
      double centre;
      memcpy(&centre, &bits, sizeof centre);
      float value = (float)centre;
      uint32_t word;
      memcpy(&word, &value, sizeof word);
      xs[i] = from32(word + (a >> 10) % 3u - 1u);
      break;
    }
    }
  }
}
int main(int argc, char ** argv) {
  char * end = NULL;
  long requested = argc > 1 ? strtol(argv[1], &end, 10) : 200;
  if (argc > 2 || requested < 1 || requested > 100000 || (end && *end)) {
    fprintf(stderr, "usage: bench-logf [repeats: 1..100000]\n");
    return 2;
  }
  if (fesetenv(FE_DFL_ENV) != 0 || fesetround(FE_TONEAREST) != 0) {
    fputs("cannot select the default environment and FE_TONEAREST\n", stderr);
    return 2;
  }
  int repeats = (int)requested;
  const char * names[] = {"common [0.25,4]", "wide positive", "neighbors of one",
      "subnormal arguments", "binary-power arguments", "table seam neighbors"};
  double * ratios = malloc((size_t)repeats * sizeof *ratios);
  if (!ratios) {
    perror("benchmark ratios");
    return 2;
  }
  printf("logf: %d alternating pairs, %d inputs; indirect calls include loop overhead\n", repeats, N);
  puts("Times are minima in ns/call; ratios are gmath/libm; pair median uses same-input pairs.");
  puts("Default environment, FE_TONEAREST; integer result checksum; identical fixed inputs in each pair.");
  puts("Results describe each input set and function; they establish no overall speed advantage.");
  puts("range                     gmath ns    libm ns  min ratio  pair median");
  for (int range = 0; range < 6; ++range) {
    inputs(range);
    for (int r = 0; r < 10; ++r) {
      (void)sample(r & 1);
      (void)sample(!(r & 1));
    }
    double best_a = 1e30, best_b = 1e30;
    for (int r = 0; r < repeats; ++r) {
      double a, b;
      if (r & 1) {
        b = sample(1);
        a = sample(0);
      }
      else {
        a = sample(0);
        b = sample(1);
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
