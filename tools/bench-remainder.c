/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Compare exact remainder calls with host libm, using identical indirect
 * calls, fixed inputs, a warm-up, and the best of several repeats. Each
 * number includes call/loop overhead; it is not an application speedup.
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
static uint64_t state = 0x952ab38d715a3c09ull;
static double unit(void) {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return (double)(state >> 11) * 0x1p-53;
}
static double now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}
static double measure(double (*fn)(double, double), int repeats) {
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
static double measuref(float (*fn)(float, float), int repeats) {
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
int main(int argc, char ** argv) {
  int repeats = argc > 1 ? atoi(argv[1]) : 100;
  if (repeats < 1) {
    return 2;
  }
  double (*volatile ours)(double, double) = gmath_fmod;
  double (*volatile host)(double, double) = fmod;
  float (*volatile oursf)(float, float) = gmath_fmodf;
  float (*volatile hostf)(float, float) = fmodf;
  const char * names[] = {"common quotients", "similar magnitudes",
      "wide exponent gap", "tiny subnormals", "power-of-two divisor",
      "dividend smaller", "large subnormal boundary"};
  puts("remainder range          type    gmath ns    libm ns    ratio");
  for (int k = 0; k < 7; ++k) {
    for (int i = 0; i < N; ++i) {
      double u = unit(), v = unit();
      switch (k) {
      case 0:
        xs[i] = u * 2000 - 1000;
        ys[i] = 0.1 + 10 * v;
        break;
      case 1:
        xs[i] = 1 + u;
        ys[i] = 1 + v;
        break;
      case 2:
        xs[i] = ldexp(1 + u, 900);
        ys[i] = ldexp(1 + v, -900);
        break;
      case 3:
        xs[i] = (1 + u * 1024) * 0x1p-1074;
        ys[i] = (1 + v * 128) * 0x1p-1074;
        break;
      case 4:
        xs[i] = u * 2000 - 1000;
        ys[i] = 2;
        break;
      case 6: {
        uint64_t a = 0x0008000000000000ull | (uint64_t)(u * 0x1p51);
        uint64_t b =
            (i & 1) ? 0x0010000000000000ull : 1 + (uint64_t)(v * 0x1p52);
        memcpy(&xs[i], &a, sizeof a);
        memcpy(&ys[i], &b, sizeof b);
        break;
      }
      default:
        xs[i] = u;
        ys[i] = 1 + v;
        break;
      }
      if (k == 2) {
        xf[i] = (float)((1 + u) * 0x1p100);
        yf[i] = (float)((1 + v) * 0x1p-100);
      }
      else if (k == 3) {
        xf[i] = (float)((1 + u * 1024) * 0x1p-149);
        yf[i] = (float)((1 + v * 128) * 0x1p-149);
      }
      else if (k == 6) {
        uint32_t a = 0x00400000u | (uint32_t)(u * 0x1p22);
        uint32_t b = (i & 1) ? 0x00800000u : 1 + (uint32_t)(v * 0x1p23);
        memcpy(&xf[i], &a, sizeof a);
        memcpy(&yf[i], &b, sizeof b);
      }
      else {
        xf[i] = (float)xs[i];
        yf[i] = (float)ys[i];
      }
    }
    (void)measure(ours, 10);
    (void)measure(host, 10);
    double a = measure(ours, repeats), b = measure(host, repeats);
    printf("%-24s f64 %10.1f %10.1f %8.2fx\n", names[k], a, b, a / b);
    (void)measuref(oursf, 10);
    (void)measuref(hostf, 10);
    a = measuref(oursf, repeats);
    b = measuref(hostf, repeats);
    printf("%-24s f32 %10.1f %10.1f %8.2fx\n", names[k], a, b, a / b);
  }
  return 0;
}
