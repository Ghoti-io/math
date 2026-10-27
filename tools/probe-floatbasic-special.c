/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw binary32 contract probe for native and cross-target builds, without gtest.
 * Hash only nearest-mode calls with no incoming flags; normalize flag constants
 * and omit sqrt's permitted inexact so hardware and portable variants agree.
 * Positive finite sqrt accuracy is required only in nearest mode; other modes
 * still require positive normal finite results and preserved state.
 */
#include <ghoti.io/math/basic.h>
#include <errno.h>
#include <fenv.h>
#include <float.h>
#include <limits.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SIGN 0x80000000u
#define ABS 0x7fffffffu
#define INF 0x7f800000u
#define QUIET 0x00400000u
#define QNAN 0x7fc00000u

static const uint32_t words[] = {
    0, SIGN, 0x3f800000u, 0xbf800000u, INF, INF | SIGN,
    QNAN, QNAN | 7, 0x7fffffffu,
    QNAN | SIGN, QNAN | SIGN | 7, 0xffffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u,
    INF | SIGN | 1, INF | SIGN | (QUIET - 1), INF | SIGN | 0x12345u};

static const struct {
  const char * name;
  float (*call)(float);
} unary[] = {
    {"floorf", gmath_floorf}, {"ceilf", gmath_ceilf},
    {"truncf", gmath_truncf}, {"roundf", gmath_roundf},
    {"rintf", gmath_rintf}, {"fabsf", gmath_fabsf}, {"sqrtf", gmath_sqrtf}};

static uint64_t hash = 0xcbf29ce484222325ull, count;
static unsigned failures;

_Static_assert(CHAR_BIT == 8 && sizeof(float) == sizeof(uint32_t) &&
    sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
    FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
    "raw float probe requires IEEE binary32 in eight-bit bytes");

static int signaling(uint32_t word) {
  return (word & ABS) > INF && (word & QUIET) == 0;
}
/* Portable flag bits: invalid=1, divide-by-zero=2, overflow=4,
 * underflow=8, inexact=16; native FE_* values never enter the hash. */
static uint32_t normalized_flags(int flags) {
  return ((flags & FE_INVALID) ? 1u : 0u) |
      ((flags & FE_DIVBYZERO) ? 2u : 0u) |
      ((flags & FE_OVERFLOW) ? 4u : 0u) |
      ((flags & FE_UNDERFLOW) ? 8u : 0u) |
      ((flags & FE_INEXACT) ? 16u : 0u);
}
static void hash_word(uint32_t word) {
  for (unsigned i = 0; i < 4; ++i) {
    hash ^= (word >> (8 * i)) & 0xffu;
    hash *= 0x100000001b3ull;
  }
}
static int prepare(int seed, int * existing) {
  if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seed) != 0) {
    fputs("floatbasic-special: cannot prepare incoming flags\n", stderr);
    return 0;
  }
  *existing = fetestexcept(FE_ALL_EXCEPT);
  errno = E2BIG;
  return 1;
}
static void check(const char * name, uint32_t x, uint32_t y,
    uint32_t result, uint32_t expected, int required, int allowed,
    int existing, int result_errno, int mode, int relaxed_positive_sqrt, int include_hash) {
  int flags = fetestexcept(FE_ALL_EXCEPT);
  int actual_mode = fegetround();
  int needed = required | existing;
  int bad_result = relaxed_positive_sqrt ? (result < 0x00800000u || result >= INF) :
      result != expected;
  if (bad_result || (flags & needed) != needed ||
      (flags & ~(needed | allowed)) != 0 || result_errno != E2BIG ||
      actual_mode != mode) {
    if (failures < 20) {
      fprintf(stderr, "floatbasic-special: %s(%08" PRIx32 ",%08" PRIx32
          ") = %08" PRIx32 " expected %08" PRIx32
          "; flags=%x required=%x allowed=%x errno=%d mode=%x expected-mode=%x relaxed-positive-root=%d\n",
          name, x, y, result, expected, flags, needed, allowed, result_errno,
          actual_mode, mode, relaxed_positive_sqrt);
    }
    ++failures;
  }
  if (include_hash) {
    hash_word(result);
    hash_word(normalized_flags(flags & ~allowed));
    ++count;
  }
}
int main(void) {
  fenv_t saved;
  int saved_errno = errno;
  if (feholdexcept(&saved) != 0) {
    fputs("floatbasic-special: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
      FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT};
  for (unsigned m = 0; m < sizeof modes / sizeof modes[0]; ++m) {
    if (fesetround(modes[m]) != 0) {
      fputs("floatbasic-special: cannot select rounding mode\n", stderr);
      ++failures;
      goto done;
    }
    for (unsigned s = 0; s < sizeof seeds / sizeof seeds[0]; ++s) {
      int include_hash = m == 0 && s == 0;
      for (unsigned f = 0; f < sizeof unary / sizeof unary[0]; ++f) {
        for (unsigned i = 0; i < sizeof words / sizeof words[0]; ++i) {
          uint32_t x = words[i], a = x & ABS, expected = x;
          int required = signaling(x) ? FE_INVALID : 0;
          int allowed = 0, existing;
          if (a > INF) {
            expected = QNAN;
          }
          else if (f == 5) { /* fabsf */
            expected = a;
          }
          else if (f == 6) { /* sqrtf */
            if ((x & SIGN) != 0 && a != 0) {
              expected = QNAN;
              required = FE_INVALID;
            }
            else if (a != 0 && a < INF) {
              allowed = FE_INEXACT;
            }
          }
          if (!prepare(seeds[s], &existing)) {
            ++failures;
            goto done;
          }
          float argument;
          memcpy(&argument, &x, sizeof argument);
          float result = unary[f].call(argument);
          int result_errno = errno;
          uint32_t result_word;
          memcpy(&result_word, &result, sizeof result_word);
          check(unary[f].name, x, 0, result_word, expected, required,
              allowed, existing, result_errno, modes[m],
              f == 6 && m != 0 && (x & SIGN) == 0 && a != 0 && a < INF, include_hash);
        }
      }
      for (unsigned i = 0; i < sizeof words / sizeof words[0]; ++i) {
        for (unsigned j = 0; j < sizeof words / sizeof words[0]; ++j) {
          uint32_t x = words[i], y = words[j], a = x & ABS;
          uint32_t expected = a > INF ? QNAN : a | (y & SIGN);
          int required = signaling(x) ? FE_INVALID : 0, existing;
          if (!prepare(seeds[s], &existing)) {
            ++failures;
            goto done;
          }
          float argument_x, argument_y;
          memcpy(&argument_x, &x, sizeof argument_x);
          memcpy(&argument_y, &y, sizeof argument_y);
          float result = gmath_copysignf(argument_x, argument_y);
          int result_errno = errno;
          uint32_t result_word;
          memcpy(&result_word, &result, sizeof result_word);
          check("copysignf", x, y, result_word, expected, required, 0,
              existing, result_errno, modes[m], 0, include_hash);
        }
      }
    }
  }
 done:
  if (fesetenv(&saved) != 0) {
    fputs("floatbasic-special: cannot restore floating environment\n", stderr);
    ++failures;
  }
  if (failures == 0) {
    printf("math.floatbasic_special.hash %016" PRIx64 "\n", hash);
    printf("math.floatbasic_special.count %" PRIu64 "\n", count);
  }
  else {
    fprintf(stderr, "floatbasic-special: %u contract checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
