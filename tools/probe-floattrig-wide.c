/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Standalone cross-target preservation probe for finite wide binary32 trig.
 * Nearest results must equal the established double path narrowed once.
 * Every rounding mode independently compares flags and preserves incoming
 * flags, errno, and mode. Only nearest results enter the portable hash.
 */
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <float.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SIGN 0x80000000u
#define ABS 0x7fffffffu
#define ONE 0x3f800000u
#define INF 0x7f800000u

_Static_assert(CHAR_BIT == 8 && sizeof(float) == sizeof(uint32_t) &&
    sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
    sizeof(double) == 8 && DBL_MANT_DIG == 53,
    "wide float trig probe requires IEEE binary32 and binary64");

static const struct function {
  const char * name;
  float (*single)(float);
  double (*baseline)(double);
} functions[] = {{"sinf", gmath_sinf, gmath_sin},
    {"cosf", gmath_cosf, gmath_cos}, {"tanf", gmath_tanf, gmath_tan}};

static uint32_t words[8192];
static size_t length;
static void add(uint32_t word) {
  uint32_t a = word & ABS;
  if (a <= ONE || a >= INF) return;
  for (size_t i = 0; i < length; ++i) {
    if (words[i] == word) return;
  }
  if (length < sizeof words / sizeof words[0]) words[length++] = word;
}
static void population(void) {
  const uint32_t mantissas[] = {0, 1, 2, 0x1fffffu, 0x3fffffu,
      0x400000u, 0x7ffffeu, 0x7fffffu};
  for (unsigned exponent = 30; exponent <= 127; ++exponent) {
    for (unsigned i = 0; i < sizeof mantissas / sizeof mantissas[0]; ++i) {
      uint32_t a = ((exponent + 127u) << 23) | mantissas[i];
      add(a);
      add(a | SIGN);
    }
    // These additional significands cover all four quadrants at every
    // exponent 30..127, independently checked with the pinned pi bounds.
    uint32_t state = 0x6d2b79f5u ^ exponent;
    for (unsigned i = 0; i < 13; ++i) {
      state ^= state << 13;
      state ^= state >> 17;
      state ^= state << 5;
      uint32_t a = ((exponent + 127u) << 23) | (state & 0x007fffffu);
      add(a);
      add(a | SIGN);
    }
  }
  /* Pinned MPFR600 inputs: k*pi/2, (k +/- 2^-12)*pi/2 (k=1..4),
   * and (k+1/2)*pi/2 (k=0..3), rounded directly to binary32.
   * Neighbors exercise tiny-phase admission and quadrant/half-phase cuts.
   * Other centers cover the >1 seam and former large reduction boundaries.
   */
  const uint32_t centers[] = {ONE, 0x49800000u, 0x4e800000u, INF - 3,
      0x3fc90fdbu, 0x40490fdbu, 0x4096cbe4u, 0x40c90fdbu,
      0x3fc9034au, 0x3fc91c6cu, 0x40490992u, 0x40491623u,
      0x4096c8c0u, 0x4096cf08u, 0x40c90cb6u, 0x40c912ffu,
      0x3f490fdbu, 0x4016cbe4u, 0x407b53d1u, 0x40afeddfu,
      /* Public wide tiny-phase and per-operation cell-uncertainty witnesses. */
      0x54a70879u, 0x621a4c41u, 0x5c63a2a9u, 0x5fae2a59u};
  for (unsigned i = 0; i < sizeof centers / sizeof centers[0]; ++i) {
    for (int delta = -2; delta <= 2; ++delta) {
      uint32_t a = centers[i] + (uint32_t)delta;
      add(a);
      add(a | SIGN);
    }
  }
  uint32_t state = 0xa341316cu;
  for (unsigned i = 0; i < 1024; ++i) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    uint32_t a = ONE + 1u + (state & 0x3fffffffu);
    if (a >= INF) a -= 0x00800000u;
    add(a | (state & SIGN));
  }
}
static uint64_t hash_word(uint64_t hash, uint32_t word) {
  for (unsigned i = 0; i < 4; ++i) {
    hash ^= (word >> (8 * i)) & 0xffu;
    hash *= 0x100000001b3ull;
  }
  return hash;
}

int main(void) {
  fenv_t saved;
  int saved_errno = errno;
  if (feholdexcept(&saved) != 0) {
    fputs("floattrig-wide: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  population();
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
      FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT};
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0, checks = 0;
  for (unsigned mode = 0; mode < sizeof modes / sizeof modes[0]; ++mode) {
    if (fesetround(modes[mode]) != 0) {
      fputs("floattrig-wide: cannot select rounding mode\n", stderr);
      ++failures;
      goto done;
    }
    for (unsigned function = 0; function < sizeof functions / sizeof functions[0]; ++function) {
      for (size_t i = 0; i < length; ++i) {
        float argument;
        memcpy(&argument, &words[i], sizeof argument);
        if (feclearexcept(FE_ALL_EXCEPT) != 0) {
          ++failures;
          goto done;
        }
        volatile double reference = functions[function].baseline((double)argument);
        volatile float expected = (float)reference;
        int baseline_flags = fetestexcept(FE_ALL_EXCEPT);
        float expected_value = expected;
        uint32_t expected_word;
        memcpy(&expected_word, &expected_value, sizeof expected_word);
        for (unsigned seed = 0; seed < sizeof seeds / sizeof seeds[0]; ++seed) {
          if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[seed]) != 0) {
            fputs("floattrig-wide: cannot prepare incoming flags\n", stderr);
            ++failures;
            goto done;
          }
          int incoming = fetestexcept(FE_ALL_EXCEPT);
          errno = E2BIG;
          volatile float result = functions[function].single(argument);
          // Snapshot immediately: no reference or metric arithmetic may
          // change the tested operation's state before these observations.
          int result_errno = errno;
          int result_flags = fetestexcept(FE_ALL_EXCEPT);
          int result_mode = fegetround();
          float result_value = result;
          uint32_t result_word;
          memcpy(&result_word, &result_value, sizeof result_word);
          int bad_bits = mode == 0 && result_word != expected_word;
          if (bad_bits || result_flags != (baseline_flags | incoming) ||
              result_errno != E2BIG || result_mode != modes[mode]) {
            if (failures < 12) {
              fprintf(stderr, "floattrig-wide: %s(%08" PRIx32 ")=%08" PRIx32
                  " baseline=%08" PRIx32 " flags=%x expected-flags=%x"
                  " errno=%d mode=%x expected-mode=%x\n", functions[function].name,
                  words[i], result_word, expected_word, (unsigned)result_flags,
                  (unsigned)(baseline_flags | incoming), result_errno,
                  (unsigned)result_mode, (unsigned)modes[mode]);
            }
            ++failures;
          }
          if (mode == 0 && seed == 0) {
            hash = hash_word(hash, result_word);
            ++count;
          }
          ++checks;
        }
      }
    }
  }
 done:
  if (fesetenv(&saved) != 0) {
    fputs("floattrig-wide: cannot restore floating environment\n", stderr);
    ++failures;
  }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.floattrig_wide.hash %016" PRIx64 "\n", hash);
    printf("math.floattrig_wide.count %" PRIu64 "\n", count);
    printf("floattrig-wide: PASS (%" PRIu64 " state checks)\n", checks);
  }
  else {
    fprintf(stderr, "floattrig-wide: %u preservation checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
