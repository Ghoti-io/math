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
 * Time gmath_atan2, gmath_exp, gmath_log, gmath_pow and gmath_hypot against the
 * host's libm, per argument range (the same method as bench-trig.c, which
 * does sin, cos and tan).  Not part of `make test` (it measures, it asserts
 * nothing); `make bench` builds and runs it.  The numbers describe this
 * machine and this compiler and mean nothing elsewhere; print them with the CPU
 * and compiler.
 *
 * Each range has 4096 arguments (or pairs) drawn from a fixed generator, so a
 * run is repeatable.  The loop is a throughput loop: the results are summed so
 * none can be dropped, and the best of several repeats is kept.  libm is
 * called through a volatile function pointer so that the compiler does not
 * fold it into a different instruction sequence than the library's own call.
 * Each figure includes about 3 ns of loop and call overhead, the same for both.
 *
 * Usage: bench-elementary [repeats]
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

typedef double (*fn1_t)(double);
typedef double (*fn2_t)(double, double);

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

/* Log-uniform magnitude in [lo, hi), with a random sign when signed_ is set. */
static double loguniform(double lo, double hi, int signed_) {
  double v = exp2(uniform(log2(lo), log2(hi)));
  return (signed_ && (next_u64() & 1)) ? -v : v;
}

static double now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

static double time1(fn1_t f, const double * xs, int repeats, double * sink) {
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

static double time2(fn2_t f, const double * xs, const double * ys, int repeats, double * sink) {
  double best = 1e30;
  for (int r = 0; r < repeats; r++) {
    double acc = 0.0;
    double t0 = now();
    for (int i = 0; i < N; i++) {
      acc += f(xs[i], ys[i]);
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

static double ours_exp(double x) { return gmath_exp(x); }
static double ours_log(double x) { return gmath_log(x); }
static double ours_pow(double x, double y) { return gmath_pow(x, y); }
static double ours_atan2(double y, double x) { return gmath_atan2(y, x); }
static double ours_hypot(double x, double y) { return gmath_hypot(x, y); }

/* Argument kinds.  Two-argument kinds fill both arrays. */
enum {
  U1,      /* uniform in [a, b] */
  L1,      /* log-uniform magnitude [a, b), random sign when b < 0 is not used: see S1 */
  S1,      /* log-uniform magnitude [a, b), random sign */
  P_TYP,   /* x log-uniform [a, b), y uniform [-5, 5] */
  P_INT,   /* x log-uniform [a, b), y a small integer in [2, 12] */
  P_WIDE,  /* x log-uniform [a, b), y uniform [-3, 3] */
  P_NEAR1, /* x = 1 + 2^-(a..b), y log-uniform to 2^(b+8) */
  P_EDGE,  /* x log-uniform [a, b), y so that the result is near overflow or underflow */
  A_ANG,   /* a point at a uniform angle and a log-uniform radius [a, b) */
  A_RATIO, /* both log-uniform [a, b), random signs */
  A_AXIS,  /* one coordinate log-uniform [a, b), the other in [0.5, 2] */
  H_ANG,   /* a point in the first quadrant at a uniform angle, radius log-uniform [a, b) */
  H_RATIO, /* x log-uniform [a, b), y = x times a uniform [0.05, 1] */
  H_SPREAD /* both log-uniform [a, b) */
};

typedef struct {
  const char * name;
  int kind;
  double a, b;
} range_t;

static void fill(const range_t * r, double * xs, double * ys) {
  for (int i = 0; i < N; i++) {
    switch (r->kind) {
    case U1:
      xs[i] = uniform(r->a, r->b);
      break;
    case L1:
      xs[i] = loguniform(r->a, r->b, 0);
      break;
    case S1:
      xs[i] = loguniform(r->a, r->b, 1);
      break;
    case P_TYP:
      xs[i] = loguniform(r->a, r->b, 0);
      ys[i] = uniform(-5, 5);
      break;
    case P_INT:
      xs[i] = loguniform(r->a, r->b, 1);
      ys[i] = (double)(2 + (int)(next_u64() % 11));
      break;
    case P_WIDE:
      xs[i] = loguniform(r->a, r->b, 0);
      ys[i] = uniform(-3, 3);
      break;
    case P_NEAR1: {
      double k = uniform(r->a, r->b);
      xs[i] = 1.0 + ((next_u64() & 1) ? -1 : 1) * exp2(-k);
      ys[i] = loguniform(1, exp2(r->b + 8), 1);
      break;
    }
    case P_EDGE: {
      double x = loguniform(r->a, r->b, 0);
      double lx = log(x);
      if (fabs(lx) < 1e-3) {
        lx = 0.5;
      }
      static const double t[] = {709.0, -745.0, 700.0, -708.0, 705.0, -740.0};
      xs[i] = x;
      ys[i] = t[next_u64() % 6] / lx;
      break;
    }
    case A_ANG: {
      double th = uniform(-3.14159, 3.14159);
      double rad = loguniform(r->a, r->b, 0);
      ys[i] = rad * sin(th);
      xs[i] = rad * cos(th);
      break;
    }
    case A_RATIO:
      ys[i] = loguniform(r->a, r->b, 1);
      xs[i] = loguniform(r->a, r->b, 1);
      break;
    case A_AXIS:
      if (next_u64() & 1) {
        ys[i] = loguniform(r->a, r->b, 1);
        xs[i] = loguniform(0.5, 2, 1);
      } else {
        xs[i] = loguniform(r->a, r->b, 1);
        ys[i] = loguniform(0.5, 2, 1);
      }
      break;
    case H_ANG: {
      double th = uniform(0, 1.5708);
      double rad = loguniform(r->a, r->b, 0);
      xs[i] = rad * cos(th);
      ys[i] = rad * sin(th);
      break;
    }
    case H_RATIO:
      xs[i] = loguniform(r->a, r->b, 1);
      ys[i] = xs[i] * uniform(0.05, 1);
      break;
    case H_SPREAD:
      xs[i] = loguniform(r->a, r->b, 1);
      ys[i] = loguniform(r->a, r->b, 1);
      break;
    }
  }
}

static void run1(const char * fname, fn1_t ours, volatile fn1_t * libm, const range_t * ranges, size_t n, int repeats,
    double * sink) {
  static double xs[N], ys[N];
  for (size_t k = 0; k < n; k++) {
    rng_state = 0x9e3779b97f4a7c15ull + k;
    fill(&ranges[k], xs, ys);
    double a = time1(ours, xs, repeats, sink);
    double b = time1(*libm, xs, repeats, sink);
    printf("%-34s %-6s %10.1f %10.1f %7.2fx\n", ranges[k].name, fname, a, b, a / b);
  }
}

static void run2(const char * fname, fn2_t ours, volatile fn2_t * libm, const range_t * ranges, size_t n, int repeats,
    double * sink) {
  static double xs[N], ys[N];
  for (size_t k = 0; k < n; k++) {
    rng_state = 0x9e3779b97f4a7c15ull + k;
    fill(&ranges[k], xs, ys);
    double a, b;
    if (strcmp(fname, "atan2") == 0) {
      a = time2(ours, ys, xs, repeats, sink);
      b = time2(*libm, ys, xs, repeats, sink);
    } else {
      a = time2(ours, xs, ys, repeats, sink);
      b = time2(*libm, xs, ys, repeats, sink);
    }
    printf("%-34s %-6s %10.1f %10.1f %7.2fx\n", ranges[k].name, fname, a, b, a / b);
  }
}

int main(int argc, char ** argv) {
  int repeats = argc > 1 ? atoi(argv[1]) : 20;
  double sink = 0.0;

  static const range_t exp_r[] = {
    {"x in [-1, 1]", U1, -1, 1},
    {"x in [-10, 10] (common)", U1, -10, 10},
    {"x in [-700, 700]", U1, -700, 700},
    {"x in [-745, -708] (subnormal result)", U1, -745, -708},
    {"x in [700, 709.7] (near overflow)", U1, 700, 709.7},
    {"|x| in 2^-60 .. 1", S1, 0x1p-60, 1},
  };
  static const range_t log_r[] = {
    {"x in [0.5, 2]", U1, 0.5, 2},
    {"x in [1e-3, 1e3] (common)", L1, 1e-3, 1e3},
    {"x in [2^-1000, 2^1000]", L1, 0x1p-1000, 0x1p1000},
    {"x = 1 +- 2^-20 .. 2^-4 (near 1)", P_NEAR1, 4, 20},
    {"x subnormal", L1, 0x1p-1074, 0x1p-1022},
  };
  static const range_t pow_r[] = {
    {"x in [0.5, 10], y in [-5, 5] (typical)", P_TYP, 0.5, 10},
    {"x in [0.1, 100], y integer 2..12", P_INT, 0.1, 100},
    {"x in [2^-300, 2^300], y in [-3, 3]", P_WIDE, 0x1p-300, 0x1p300},
    {"x near 1, y huge", P_NEAR1, 10, 30},
    {"result near overflow / underflow", P_EDGE, 0.1, 10},
  };
  static const range_t atan2_r[] = {
    {"angle uniform, radius 2^-30 .. 2^30", A_ANG, 0x1p-30, 0x1p30},
    {"ratio 2^-60 .. 2^60", A_RATIO, 0x1p-60, 0x1p60},
    {"near an axis (ratio 1e-6 .. 1e-1)", A_AXIS, 1e-6, 1e-1},
    {"subnormal and tiny", A_RATIO, 0x1p-1074, 0x1p-1000},
    {"mixed exponents 2^-1000 .. 2^1000", A_RATIO, 0x1p-1000, 0x1p1000},
  };
  static const range_t hypot_r[] = {
    {"similar magnitude (angle uniform)", H_ANG, 0x1p-30, 0x1p30},
    {"x log-uniform, y/x in [0.05, 1]", H_RATIO, 0x1p-500, 0x1p500},
    {"independent exponents 2^-1070 .. 2^1022", H_SPREAD, 0x1p-1070, 0x1p1022},
    {"independent exponents 2^-20 .. 2^20", H_SPREAD, 0x1p-20, 0x1p20},
  };

  /* Warm-up: a few tenths of a second of work, so that the first range is not timed while the clock ramps. */
  {
    double t0 = now();
    volatile double w = 0.5;
    while (now() - t0 < 0.3) {
      for (int i = 0; i < 2000; i++) {
        w = w + gmath_log(1.0 + w) * 1e-9 + 0.5;
        w = w - gmath_exp(w * 1e-3) * 1e-9;
      }
    }
    sink += w;
  }

  volatile fn1_t libm_exp = exp, libm_log = log;
  volatile fn2_t libm_pow = pow, libm_atan2 = atan2, libm_hypot = hypot;

  printf("%-34s %-6s %10s %10s %8s\n", "range", "fn", "gmath ns", "libm ns", "ratio");
  run1("exp", ours_exp, &libm_exp, exp_r, sizeof exp_r / sizeof exp_r[0], repeats, &sink);
  run1("log", ours_log, &libm_log, log_r, sizeof log_r / sizeof log_r[0], repeats, &sink);
  run2("pow", ours_pow, &libm_pow, pow_r, sizeof pow_r / sizeof pow_r[0], repeats, &sink);
  run2("atan2", ours_atan2, &libm_atan2, atan2_r, sizeof atan2_r / sizeof atan2_r[0], repeats, &sink);
  run2("hypot", ours_hypot, &libm_hypot, hypot_r, sizeof hypot_r / sizeof hypot_r[0], repeats, &sink);
  if (sink == 12345.678) {
    puts("");
  }
  return 0;
}
