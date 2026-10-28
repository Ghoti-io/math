/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Host output/timing comparison, not an independent accuracy oracle.
 */
#define _POSIX_C_SOURCE 200809L
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
static double dx[N];
static float fx[N];
static volatile uint64_t sink;
static double (*volatile dcall)(double);
static float (*volatile fcall)(float);
static uint64_t bits64(double x) {
  uint64_t w;
  memcpy(&w, &x, 8);
  return w;
}
static uint32_t bits32(float x) {
  uint32_t w;
  memcpy(&w, &x, 4);
  return w;
}
static uint64_t rng(uint64_t * s) {
  *s ^= *s << 13;
  *s ^= *s >> 7;
  *s ^= *s << 17;
  return *s;
}
static uint64_t tick(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    exit(2);
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static void setup(int mode, int seeded) {
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) ||
      feraiseexcept(seeded ? (FE_UNDERFLOW | FE_INEXACT) : 0))
    exit(2);
  errno = seeded ? 733 : 0;
}
static uint64_t measure(
    unsigned width, int host, int mode, int seeded, int invalid) {
  dcall = host ? nearbyint : gmath_nearbyint;
  fcall = host ? nearbyintf : gmath_nearbyintf;
  setup(mode, seeded);
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  uint64_t sum = 0, start = tick();
  if (width == 64) {
    for (unsigned i = 0; i < N; i++)
      sum += bits64(dcall(dx[i]));
  }
  else {
    for (unsigned i = 0; i < N; i++)
      sum += bits32(fcall(fx[i]));
  }
  uint64_t elapsed = tick() - start;
  int error = errno, flags = fetestexcept(FE_ALL_EXCEPT), round = fegetround();
  sink += sum;
  if (error != (seeded ? 733 : 0) ||
      flags != (incoming | (invalid ? FE_INVALID : 0)) || round != mode) {
    fprintf(stderr,
        "nearby batch state differs width%u host%d mode%d flags%x/%x errno%d\n",
        width, host, mode, flags, incoming | (invalid ? FE_INVALID : 0), error);
    exit(2);
  }
  return elapsed;
}
static int cmpu(const void * a, const void * b) {
  uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return (x > y) - (x < y);
}
static int cmpd(const void * a, const void * b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
int main(int argc, char ** argv) {
  int validate = argc == 2 && !strcmp(argv[1], "--validate-only");
  if (argc != 1 && !validate)
    return 2;
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  const char * mn[] = {"nearest", "down", "up", "zero"};
  const char * names[] = {"normal", "half-ties", "tiny-normal", "subnormal",
      "large-integral", "signed-zero", "infinity", "qNaN", "sNaN"};
  uint64_t state = UINT64_C(0x6e6561726279696e);
  puts("8 paired warmups;401 alternating pairs4096; integer timestamps; "
       "absolute median ns/call and paired p10/median/p90; includes "
       "call/loop/checksum/clock and amortized first exceptions");
  for (unsigned width = 64; width >= 32; width -= 32)
    for (unsigned range = 0; range < 9; range++) {
      unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
      uint64_t sign = UINT64_C(1) << (width - 1), hidden = UINT64_C(1) << p,
               inf = (width == 64 ? UINT64_C(2047) : UINT64_C(255)) << p;
      for (unsigned i = 0; i < N; i++) {
        uint64_t z = rng(&state), word;
        if (range < 2) {
          double v = range == 0 ? (double)((int)(z % 200001) - 100000) / 16.0
                                : (double)((int)(z % 2001) - 1000) + 0.5;
          word = width == 64 ? bits64(v) : bits32((float)v);
        }
        else if (range == 2)
          word = ((uint64_t)(bias / 2) << p) | (z & (hidden - 1)) | (z & sign);
        else if (range == 3)
          word = (z & (hidden - 1)) | 1u | (z & sign);
        else if (range == 4)
          word = (inf - 1 - (z & 4095u)) | (z & sign);
        else if (range == 5)
          word = z & sign;
        else if (range == 6)
          word = inf | (z & sign);
        else
          word = inf | (z & sign) | (range == 7 ? hidden >> 1 : 0) |
              (z & ((hidden >> 1) - 1)) | 1u;
        if (width == 64)
          memcpy(&dx[i], &word, 8);
        else {
          uint32_t w = (uint32_t)word;
          memcpy(&fx[i], &w, 4);
        }
      }
      for (unsigned mode = 0; mode < 4; mode++)
        for (int seeded = 0; seeded < 2; seeded++) {
          dcall = nearbyint;
          fcall = nearbyintf;
          for (unsigned i = 0; i < N; i++) {
            setup(modes[mode], seeded);
            int incoming = fetestexcept(FE_ALL_EXCEPT);
            uint64_t own, host;
            if (width == 64)
              own = bits64(gmath_nearbyint(dx[i]));
            else
              own = bits32(gmath_nearbyintf(fx[i]));
            if (errno != (seeded ? 733 : 0) || fegetround() != modes[mode] ||
                fetestexcept(FE_ALL_EXCEPT) !=
                    (incoming | (range == 8 ? FE_INVALID : 0)))
              return 2;
            setup(modes[mode], seeded);
            if (width == 64)
              host = bits64(dcall(dx[i]));
            else
              host = bits32(fcall(fx[i]));
            if (errno != (seeded ? 733 : 0) || fegetround() != modes[mode] ||
                fetestexcept(FE_ALL_EXCEPT) !=
                    (incoming | (range == 8 ? FE_INVALID : 0)))
              return 2;
            if (range >= 7) {
              if (own != (inf | (hidden >> 1)) || (host & (sign - 1)) <= inf)
                return 2;
            }
            else if (own != host)
              return 2;
          }
          if (validate)
            continue;
          for (unsigned w = 0; w < 8; w++) {
            (void)measure(width, w & 1, modes[mode], seeded, range == 8);
            (void)measure(width, !(w & 1), modes[mode], seeded, range == 8);
          }
          uint64_t own[PAIRS], host[PAIRS];
          double ratios[PAIRS];
          for (unsigned pair = 0; pair < PAIRS; pair++) {
            if (pair & 1) {
              host[pair] = measure(width, 1, modes[mode], seeded, range == 8);
              own[pair] = measure(width, 0, modes[mode], seeded, range == 8);
            }
            else {
              own[pair] = measure(width, 0, modes[mode], seeded, range == 8);
              host[pair] = measure(width, 1, modes[mode], seeded, range == 8);
            }
            if (!host[pair] || fesetround(FE_TONEAREST))
              return 2;
            ratios[pair] = (double)own[pair] / (double)host[pair];
          }
          qsort(own, PAIRS, sizeof *own, cmpu);
          qsort(host, PAIRS, sizeof *host, cmpu);
          qsort(ratios, PAIRS, sizeof *ratios, cmpd);
          printf("nearby %u %s %s %s own %.3f host %.3f ratio %.3f %.3f %.3f\n",
              width, names[range], mn[mode], seeded ? "UF/IX" : "clean",
              (double)own[PAIRS / 2] / N, (double)host[PAIRS / 2] / N,
              ratios[PAIRS / 10], ratios[PAIRS / 2], ratios[9 * PAIRS / 10]);
        }
    }
  if (validate)
    puts("nearby144 cases per-input value/state checks pass");
  return sink == UINT64_C(0xdeadbeef) ? 1 : 0;
}
