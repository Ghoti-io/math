/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Ghoti.io Math is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Ghoti.io Math is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * @file
 *
 * Time gmath_sin, gmath_cos and gmath_tan against the host's libm, per
 * argument range.  Not part of `make test` (it measures, it asserts nothing);
 * `make bench` builds and runs it.  The numbers describe this machine and this
 * compiler and mean nothing elsewhere; print them with the CPU and compiler.
 *
 * Each range has 4096 arguments drawn from a fixed generator, so a run is
 * repeatable.  The loop is a throughput loop: the results are summed so none
 * can be dropped, and the best of several repeats is kept.  libm is called
 * through a volatile function pointer so that the compiler does not fold it
 * into a different instruction sequence than the library's own call.
 *
 * Usage: bench-trig [repeats]
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

typedef double (*fn_t)(double);

static uint64_t rng_state = 0x9e3779b97f4a7c15ull;

static uint64_t next_u64(void) {
  rng_state ^= rng_state << 13;
  rng_state ^= rng_state >> 7;
  rng_state ^= rng_state << 17;
  return rng_state;
}

static double uniform(double lo, double hi) {
  double u = (double)(next_u64() >> 11) * 0x1p-53;
  return lo + (hi - lo) * u;
}

/* Log-uniform magnitude in [lo, hi), random sign. */
static double loguniform(double lo, double hi) {
  double e = uniform(log2(lo), log2(hi));
  double v = exp2(e);
  return (next_u64() & 1) ? -v : v;
}

static double now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

static double time_one(fn_t f, const double * xs, int repeats, double * sink) {
  double best = 1e30;
  for (int r = 0; r < repeats; r++) {
    double acc = 0.0;
    double t0 = now();
    for (int i = 0; i < N; i++) {
      acc += f(xs[i]);
    }
    double t1 = now();
    *sink += acc;
    double ns = (t1 - t0) * 1e9 / N;
    if (ns < best) {
      best = ns;
    }
  }
  return best;
}

static double ours_sin(double x) { return gmath_sin(x); }
static double ours_cos(double x) { return gmath_cos(x); }
static double ours_tan(double x) { return gmath_tan(x); }

int main(int argc, char ** argv) {
  int repeats = argc > 1 ? atoi(argv[1]) : 20;
  static double xs[N];
  double sink = 0.0;
  static const struct {
    const char * name;
    double lo, hi;
    int kind; /* 0 uniform in +-hi, 1 log-uniform magnitude [lo, hi) */
  } ranges[] = {
    {"|x| <= pi/4", 0, 0.78, 0},
    {"pi/4 .. 100", 0.8, 100, 1},
    {"100 .. 1e4", 100, 1e4, 1},
    {"1e4 .. 1e6", 1e4, 1e6, 1},
    {"1e6 .. 1e9", 1e6, 1e9, 1},
    {"1e9 .. 1e300", 1e9, 1e300, 1},
    {"~1e300", 1e300, 1.0000001e300, 1},
  };
  static const struct {
    const char * name;
    fn_t ours;
    volatile fn_t * libm_ptr;
  } fns[3] = {{"sin", ours_sin, NULL}, {"cos", ours_cos, NULL}, {"tan", ours_tan, NULL}};
  volatile fn_t libm_fns[3] = {sin, cos, tan};
  (void)fns[0].libm_ptr;

  /* Warm-up: a few tenths of a second of work, so that the first range is not timed while the clock ramps. */
  {
    double t0 = now();
    volatile double w = 0.5;
    while (now() - t0 < 0.3) {
      for (int i = 0; i < 2000; i++) {
        w = w + gmath_sin(w) * 1e-9 + 0.5;
      }
    }
    sink += w;
  }

  printf("%-14s %-4s %10s %10s %8s\n", "range", "fn", "gmath ns", "libm ns", "ratio");
  for (size_t k = 0; k < sizeof ranges / sizeof ranges[0]; k++) {
    rng_state = 0x9e3779b97f4a7c15ull + k;
    for (int i = 0; i < N; i++) {
      if (ranges[k].kind == 0) {
        xs[i] = uniform(-ranges[k].hi, ranges[k].hi);
      } else {
        xs[i] = loguniform(ranges[k].lo, ranges[k].hi);
      }
    }
    for (int f = 0; f < 3; f++) {
      double a = time_one(fns[f].ours, xs, repeats, &sink);
      double b = time_one(libm_fns[f], xs, repeats, &sink);
      printf("%-14s %-4s %10.1f %10.1f %7.1fx\n", ranges[k].name, fns[f].name, a, b, a / b);
    }
  }
  if (sink == 12345.678) {
    puts("");
  }
  return 0;
}
