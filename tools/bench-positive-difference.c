/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Scalar nearest host comparison. External Fraction checks certify the actual
 * emitted workload references before final timing; host errno is not parity.
 */
#define _POSIX_C_SOURCE 200809L
#include "../tests/fp_controls.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define N 4096
#define PAIRS 401
static double dx[N], dy[N];
static float fx[N], fy[N];
static uint64_t rx[N], ry[N], own_target[N], host_target[N];
static unsigned classes[N];
static volatile uint64_t sink;
static double (*volatile dd)(double, double);
static float (*volatile ff)(float, float);
static uint64_t tick(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t)) {
    exit(2);
  }
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static uint64_t rng(uint64_t * s) {
  *s ^= *s << 13;
  *s ^= *s >> 7;
  *s ^= *s << 17;
  return *s;
}
static int cmpu(const void * a, const void * b) {
  uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return (x > y) - (x < y);
}
static int cmpd(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
static void setup(int seeded) {
  if (fesetround(FE_TONEAREST) || feclearexcept(FE_ALL_EXCEPT) ||
      (seeded && feraiseexcept(FE_UNDERFLOW | FE_INEXACT))) {
    exit(2);
  }
  errno = seeded ? 733 : 0;
}
static void select_api(int host) {
  dd = host ? fdim : gmath_fdim;
  ff = host ? fdimf : gmath_fdimf;
}
static uint64_t call(unsigned api, unsigned i) {
  if (!api) {
    double r = dd(dx[i], dy[i]);
    uint64_t w;
    memcpy(&w, &r, 8);
    return w;
  }
  float r = ff(fx[i], fy[i]);
  uint32_t w;
  memcpy(&w, &r, 4);
  return w;
}
static int native_flags(unsigned f) {
  return ((f & 1u) ? FE_INVALID : 0) | ((f & 2u) ? FE_INEXACT : 0) |
      ((f & 4u) ? FE_OVERFLOW : 0);
}
static uint64_t measure(
    unsigned api, int host, int seeded, int added, uint64_t expected) {
  select_api(host);
  setup(seeded);
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  uint64_t controls = gmath_test_controls();
  uint64_t hash = 0, start = tick();
  for (unsigned i = 0; i < N; ++i) {
    hash += call(api, i);
  }
  uint64_t elapsed = tick() - start;
  sink ^= hash;
  if (hash != expected) {
    fputs("fdim timed checksum mismatch\n", stderr);
    exit(2);
  }
  if (fegetround() != FE_TONEAREST || gmath_test_controls() != controls ||
      (!host &&
          (errno != (seeded ? 733 : 0) ||
              fetestexcept(FE_ALL_EXCEPT) != (incoming | added)))) {
    fputs("fdim timed state mismatch\n", stderr);
    exit(2);
  }
  return elapsed;
}
static void reference(unsigned api, unsigned i, uint64_t inf, uint64_t quiet,
    uint64_t sign, uint64_t minimum) {
  uint64_t a = rx[i] & (sign - 1), b = ry[i] & (sign - 1);
  select_api(1);
  setup(0);
  host_target[i] = call(api, i);
  int observed = fetestexcept(FE_ALL_EXCEPT);
  if (a > inf || b > inf) {
    own_target[i] = inf | quiet;
    classes[i] =
        ((a > inf && !(rx[i] & quiet)) || (b > inf && !(ry[i] & quiet))) ? 1u
                                                                         : 0u;
    return;
  }
  uint64_t target = host_target[i];
  if ((target & sign) || target > inf) {
    fputs("fdim host numerical class mismatch\n", stderr);
    exit(2);
  }
  own_target[i] = target;
  if (a == inf || b == inf || target < minimum) {
    classes[i] = 0;
  }
  else if (target == inf) {
    classes[i] = 6;
  }
  else {
    classes[i] = (observed & FE_INEXACT) ? 2u : 0u;
  }
}
int main(int argc, char ** argv) {
  int emit = argc == 2 && !strcmp(argv[1], "--emit-reference"),
      validate = argc == 2 && !strcmp(argv[1], "--validate-only");
  if (argc != 1 && !emit && !validate) {
    return 2;
  }
  const char * names[] = {"fdim", "fdimf"};
  const char * ranges[] = {"ordinary", "ordered-zero", "cancellation",
      "far-gap", "subnormal", "tie-neighbors", "overflow", "infinity", "qNaN",
      "sNaN"};
  if (emit) {
    printf("fdim.reference N%u pairs%u ranges10 APIs2\n", (unsigned)N,
        (unsigned)PAIRS);
  }
  else {
    printf(
        "8 paired warmups;%u alternating pairs%u; nearest only; integer "
        "timestamps; median ns/call and paired p10/median/p90; "
        "call/loop/checksum/clock and first-exception amortization included\n",
        (unsigned)PAIRS, (unsigned)N);
    printf("fdim.identity compiler %s built %s %s\n", __VERSION__, __DATE__,
        __TIME__);
    puts("fdim.comparison host-libm; host NaN payload/errno/extra flags "
         "unpromised");
  }
  uint64_t state = UINT64_C(0x6664696d70616972);
  for (unsigned api = 0; api < 2; ++api) {
    unsigned p = api ? 23u : 52u, bias = api ? 127u : 1023u,
             width = api ? 32u : 64u;
    uint64_t sign = UINT64_C(1) << (width - 1), hidden = UINT64_C(1) << p,
             quiet = hidden >> 1,
             inf = (api ? UINT64_C(255) : UINT64_C(2047)) << p,
             minimum = hidden;
    for (unsigned range = 0; range < 10; ++range) {
      for (unsigned i = 0; i < N; ++i) {
        uint64_t z = rng(&state), v = rng(&state), x, y;
        if (range == 0) {
          x = ((uint64_t)((int)bias + (int)(z % 9) - 4) << p) |
              (z & (hidden - 1)) | (z & sign);
          y = ((uint64_t)((int)bias + (int)(v % 9) - 4) << p) |
              (v & (hidden - 1)) | (v & sign);
        }
        else if (range == 1) {
          x = ((uint64_t)bias << p) | (z & (hidden - 1)) | (z & sign);
          y = (x & sign) ? x - 1 : x + 1;
        }
        else if (range == 2) {
          x = ((uint64_t)((int)bias + (int)(z % 17) - 8) << p) |
              (z & (hidden - 1));
          y = x - 1;
          if (i & 1) {
            uint64_t t = x;
            x = y | sign;
            y = t | sign;
          }
        }
        else if (range == 3) {
          unsigned gap = p + 1 + (unsigned)(z % 4);
          x = ((uint64_t)bias << p) | (z & (hidden - 1));
          y = ((uint64_t)(bias - gap) << p) | (v & (hidden - 1)) | (v & sign);
        }
        else if (range == 4) {
          x = (z & (hidden - 1)) | 1;
          y = (v & (hidden - 1)) | (v & sign);
        }
        else if (range == 5) {
          unsigned side = (i / 3) % 2;
          x = ((uint64_t)bias << p) | ((i / 6) & 1u);
          y = (((uint64_t)(bias - p - 1 - side) << p) + (i % 3) - 1) |
              (side ? 0 : sign);
        }
        else if (range == 6) {
          x = inf - 1;
          y = sign | (((uint64_t)(bias + bias - p - 1) << p) + (i % 3) - 1);
          if (i % 16 == 0) {
            x = (uint64_t)(bias + bias) << p;
            y = x | sign;
          }
        }
        else if (range == 7) {
          switch (i % 4) {
          case 0:
            x = inf;
            y = inf;
            break;
          case 1:
            x = inf;
            y = sign | inf;
            break;
          case 2:
            x = sign | inf;
            y = 0;
            break;
          default:
            x = 0;
            y = sign | inf;
            break;
          }
        }
        else {
          x = inf | (z & (quiet - 1)) | 1 | (z & sign) |
              (range == 8 ? quiet : 0);
          y = (range == 9 && i % 4 < 2)
              ? inf | quiet
              : ((uint64_t)bias << p) | (v & (hidden - 1));
          if (i & 1) {
            uint64_t t = x;
            x = y;
            y = t;
          }
        }
        rx[i] = x;
        ry[i] = y;
        if (!api) {
          memcpy(&dx[i], &x, 8);
          memcpy(&dy[i], &y, 8);
        }
        else {
          uint32_t a = (uint32_t)x, b = (uint32_t)y;
          memcpy(&fx[i], &a, 4);
          memcpy(&fy[i], &b, 4);
        }
        reference(api, i, inf, quiet, sign, minimum);
        if (emit) {
          printf("fdim.reference %s %s %u %016" PRIx64 " %016" PRIx64
                 " %016" PRIx64 " %u\n",
              names[api], ranges[range], i, x, y, own_target[i], classes[i]);
        }
      }
      if (emit) {
        continue;
      }
      for (int seeded = 0; seeded < 2; ++seeded) {
        uint64_t own_hash = 0, host_hash = 0;
        int added = 0;
        for (unsigned i = 0; i < N; ++i) {
          int want = native_flags(classes[i]);
          added |= want;
          select_api(0);
          setup(seeded);
          int incoming = fetestexcept(FE_ALL_EXCEPT);
          uint64_t controls = gmath_test_controls();
          uint64_t got = call(api, i);
          int error = errno, flags = fetestexcept(FE_ALL_EXCEPT),
              mode = fegetround();
          if (got != own_target[i] || error != (seeded ? 733 : 0) ||
              flags != (incoming | want) || mode != FE_TONEAREST ||
              gmath_test_controls() != controls) {
            fputs("fdim own per-input value/state mismatch\n", stderr);
            return 2;
          }
          own_hash += got;
          select_api(1);
          setup(seeded);
          controls = gmath_test_controls();
          got = call(api, i);
          if (got != host_target[i] || gmath_test_controls() != controls ||
              fegetround() != FE_TONEAREST) {
            fputs("fdim host per-input result mismatch\n", stderr);
            return 2;
          }
          host_hash += got;
        }
        if (validate) {
          continue;
        }
        for (unsigned warm = 0; warm < 8; ++warm) {
          (void)measure(
              api, warm & 1, seeded, added, (warm & 1) ? host_hash : own_hash);
          (void)measure(api, !(warm & 1), seeded, added,
              !(warm & 1) ? host_hash : own_hash);
        }
        uint64_t own[PAIRS], host[PAIRS];
        double ratios[PAIRS];
        for (unsigned pair = 0; pair < PAIRS; ++pair) {
          if (pair & 1) {
            host[pair] = measure(api, 1, seeded, added, host_hash);
            own[pair] = measure(api, 0, seeded, added, own_hash);
          }
          else {
            own[pair] = measure(api, 0, seeded, added, own_hash);
            host[pair] = measure(api, 1, seeded, added, host_hash);
          }
          if (!host[pair] || fesetround(FE_TONEAREST)) {
            return 2;
          }
          ratios[pair] = (double)own[pair] / (double)host[pair];
        }
        qsort(own, PAIRS, sizeof *own, cmpu);
        qsort(host, PAIRS, sizeof *host, cmpu);
        qsort(ratios, PAIRS, sizeof *ratios, cmpd);
        printf("fdim %s %s %s own %.3f host %.3f ratio %.3f %.3f %.3f\n",
            names[api], ranges[range], seeded ? "UF/IX" : "clean",
            (double)own[PAIRS / 2] / N, (double)host[PAIRS / 2] / N,
            ratios[PAIRS / 10], ratios[PAIRS / 2], ratios[9 * PAIRS / 10]);
      }
    }
  }
  if (validate) {
    puts("fdim40 cases per-input guards pass");
  }
  return sink == UINT64_C(0xdeadbeef) ? 1 : 0;
}
