/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Oracle-free binary32 natural-logarithm contracts. Exact decimal powers through
 * 10^10 and special/domain cases have exact-bit expectations. Other positive finite
 * inputs require normal nonzero results of the proper sign and inexact.
 * Hash payload: nearest/no incoming flags, result words plus normalized flags.
 * Errno and mode are asserted per call, outside the payload; no float-return
 * constructor transports raw input NaNs.
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
#define INF 0x7f800000u
#define QUIET 0x00400000u
#define QNAN 0x7fc00000u
#define ONE 0x3f800000u
#define MIN_NORMAL 0x00800000u

_Static_assert(CHAR_BIT == 8 && sizeof(float) == 4 &&
    sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
    FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
    "raw log10f probe requires IEEE binary32 in eight-bit bytes");

static const uint32_t raw_cases[] = {
    0, SIGN, INF, INF | SIGN,
    QNAN, QNAN | 7, 0x7fffffffu, QNAN | SIGN, QNAN | SIGN | 7, 0xffffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u,
    INF | SIGN | 1, INF | SIGN | (QUIET - 1), INF | SIGN | 0x12345u,
    ONE, SIGN | ONE, ONE - 2, ONE - 1, ONE + 1, ONE + 2,
    SIGN | (ONE - 2), SIGN | (ONE - 1), SIGN | (ONE + 1), SIGN | (ONE + 2),
    1, SIGN | 1, 2, SIGN | 2, 0x007fffffu, 0x807fffffu,
    MIN_NORMAL, SIGN | MIN_NORMAL, MIN_NORMAL + 1, SIGN | (MIN_NORMAL + 1),
    0x7f7fffffu, 0xff7fffffu};
/* Independently representable 10^n inputs and exact binary32 integers n. */
static const uint32_t decimal_arguments[] = {0x3f800000u, 0x41200000u,
    0x42c80000u, 0x447a0000u, 0x461c4000u, 0x47c35000u,
    0x49742400u, 0x4b189680u, 0x4cbebc20u, 0x4e6e6b28u, 0x501502f9u};
static const uint32_t decimal_results[] = {0, 0x3f800000u, 0x40000000u,
    0x40400000u, 0x40800000u, 0x40a00000u, 0x40c00000u,
    0x40e00000u, 0x41000000u, 0x41100000u, 0x41200000u};
static int exact_decimal(uint32_t argument, uint32_t * result) {
  for (unsigned i = 0; i < sizeof decimal_arguments / sizeof decimal_arguments[0]; ++i) {
    if (argument == decimal_arguments[i]) {
      *result = decimal_results[i];
      return 1;
    }
  }
  return 0;
}
static void append(uint32_t * cases, unsigned * count, uint32_t word) {
  for (unsigned i = 0; i < *count; ++i) {
    if (cases[i] == word) return;
  }
  cases[(*count)++] = word;
}
/* Construct power-of-two ARGUMENTS. Their logarithms are not exact exceptions. */
static uint32_t binary_power_argument(int exponent) {
  return exponent < -126 ? 1u << (unsigned)(exponent + 149) :
      (uint32_t)(exponent + 127) << 23;
}
static uint32_t normalized_flags(int flags) {
  return ((flags & FE_INVALID) ? 1u : 0u) |
      ((flags & FE_DIVBYZERO) ? 2u : 0u) |
      ((flags & FE_OVERFLOW) ? 4u : 0u) |
      ((flags & FE_UNDERFLOW) ? 8u : 0u) |
      ((flags & FE_INEXACT) ? 16u : 0u);
}
static uint64_t hash_word(uint64_t hash, uint32_t word) {
  for (unsigned i = 0; i < 4; ++i) {
    hash ^= (word >> (8 * i)) & 0xffu;
    hash *= 0x100000001b3ull;
  }
  return hash;
}
int main(void) {
  int saved_errno = errno;
  uint32_t cases[sizeof raw_cases / sizeof raw_cases[0] + 2 * 277 + 4 * 23 + 2 * 5 * 12];
  unsigned case_count = 0;
  for (unsigned i = 0; i < sizeof raw_cases / sizeof raw_cases[0]; ++i) {
    append(cases, &case_count, raw_cases[i]);
  }
  for (int exponent = -149; exponent <= 127; ++exponent) {
    uint32_t word = binary_power_argument(exponent);
    append(cases, &case_count, word);
    append(cases, &case_count, word | SIGN);
  }
  for (unsigned length = 1; length <= 23; ++length) {
    uint32_t low = 1u << (length - 1), high = (1u << length) - 1u;
    uint32_t middle = low | (low >> 1);
    append(cases, &case_count, high);
    append(cases, &case_count, high | SIGN);
    append(cases, &case_count, middle);
    append(cases, &case_count, middle | SIGN);
  }
  for (unsigned i = 0; i < sizeof decimal_arguments / sizeof decimal_arguments[0]; ++i) {
    for (int delta = -2; delta <= 2; ++delta) {
      uint32_t word = decimal_arguments[i] + (uint32_t)delta;
      append(cases, &case_count, word);
      append(cases, &case_count, word | SIGN);
    }
  }
  // Nearest 10^11 is not exact: its true logarithm needs FE_INEXACT.
  for (int delta = -2; delta <= 2; ++delta) {
    uint32_t word = 0x51ba43b7u + (uint32_t)delta;
    append(cases, &case_count, word);
    append(cases, &case_count, word | SIGN);
  }
  fenv_t saved;
  if (feholdexcept(&saved) != 0) {
    fputs("log10f-special: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0;
  if (fesetenv(FE_DFL_ENV) != 0) {
    fputs("log10f-special: cannot select default floating environment\n", stderr);
    ++failures;
    goto done;
  }
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
      FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT};
  for (unsigned m = 0; m < sizeof modes / sizeof modes[0]; ++m) {
    if (fesetround(modes[m]) != 0) {
      ++failures;
      goto done;
    }
    for (unsigned s = 0; s < sizeof seeds / sizeof seeds[0]; ++s) {
      for (unsigned i = 0; i < case_count; ++i) {
        uint32_t word = cases[i], a = word & ABS;
        uint32_t expected = 0;
        int required = 0, exact = 1;
        if (a > INF) {
          expected = QNAN;
          required = (a & QUIET) == 0 ? FE_INVALID : 0;
        }
        else if (a == 0) {
          expected = INF | SIGN;
          required = FE_DIVBYZERO;
        }
        else if (word & SIGN) {
          expected = QNAN;
          required = FE_INVALID;
        }
        else if (a == INF) {
          expected = INF;
        }
        else if (exact_decimal(word, &expected)) {
          // Every represented decimal power is exact in every mode.
        }
        else {
          exact = 0;
          required = FE_INEXACT;
        }
        float argument;
        memcpy(&argument, &word, sizeof argument);
        if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[s]) != 0) {
          ++failures;
          goto done;
        }
        int existing = fetestexcept(FE_ALL_EXCEPT);
        errno = E2BIG;
        float result = gmath_log10f(argument);
        int result_errno = errno;
        int result_flags = fetestexcept(FE_ALL_EXCEPT), result_mode = fegetround();
        uint32_t result_word;
        memcpy(&result_word, &result, sizeof result_word);
        uint32_t result_magnitude = result_word & ABS;
        int expected_negative = word < ONE;
        int bad_result = exact ? result_word != expected :
            (result_magnitude < MIN_NORMAL || result_magnitude >= INF ||
             ((result_word & SIGN) != 0) != expected_negative);
        int needed = required | existing;
        if (bad_result || (result_flags & needed) != needed ||
            (result_flags & ~needed) != 0 || result_errno != E2BIG || result_mode != modes[m]) {
          if (failures < 20) {
            fprintf(stderr, "log10f-special: input=%08" PRIx32 " result=%08" PRIx32
                " expected=%08" PRIx32 " exact=%d flags=%x required=%x errno=%d mode=%x expected-mode=%x\n",
                word, result_word, expected, exact, (unsigned)result_flags,
                (unsigned)needed, result_errno, (unsigned)result_mode, (unsigned)modes[m]);
          }
          ++failures;
        }
        if (m == 0 && s == 0) {
          hash = hash_word(hash, result_word);
          hash = hash_word(hash, normalized_flags(result_flags));
          ++count;
        }
      }
    }
  }
 done:
  if (fesetenv(&saved) != 0) {
    fputs("log10f-special: cannot restore floating environment\n", stderr);
    ++failures;
  }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.log10f_special.hash %016" PRIx64 "\n", hash);
    printf("math.log10f_special.count %" PRIu64 "\n", count);
  }
  else {
    fprintf(stderr, "log10f-special: %u contract checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
