/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Oracle-free raw binary32 natural-exponential contracts. Only zeros, special values, classified tails and nearest tiny inputs have
 * exact-bit expectations; finite nonzero arguments require inexact.
 * All state is captured before output or any reference arithmetic.
 * Hash payload: nearest mode/no incoming flags, result words plus normalized
 * exception flags only. Errno and rounding mode are asserted on every call
 * and deliberately excluded from the payload.
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
    "raw expf probe requires IEEE binary32 in eight-bit bytes");

/* Certified by tools/oracle/gen_corpus_expf.py using directed MPFR and mpmath. */
#define OVERFLOW_FIRST 0x42b17218u
#define ZERO_LAST 0xc2cff1b5u
#define SUBNORMAL_LAST 0xc2aeac50u
static const uint32_t raw_cases[] = {
    0, SIGN, INF, INF | SIGN,
    QNAN, QNAN | 7, 0x7fffffffu, QNAN | SIGN, QNAN | SIGN | 7, 0xffffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u,
    INF | SIGN | 1, INF | SIGN | (QUIET - 1), INF | SIGN | 0x12345u,
    ONE, SIGN | ONE, 0x40000000u, 0xc0000000u,
    1, SIGN | 1, 0x007fffffu, 0x807fffffu, MIN_NORMAL, SIGN | MIN_NORMAL,
    0x327fffffu, 0xb27fffffu, 0x32800000u, 0xb2800000u,
    0x32800001u, 0xb2800001u, 0x7f7fffffu, 0xff7fffffu};
static void append(uint32_t * cases, unsigned * count, uint32_t word) {
  for (unsigned i = 0; i < *count; ++i) {
    if (cases[i] == word) return;
  }
  cases[(*count)++] = word;
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
  uint32_t cases[sizeof raw_cases / sizeof raw_cases[0] + 15];
  unsigned case_count = 0;
  for (unsigned i = 0; i < sizeof raw_cases / sizeof raw_cases[0]; ++i) {
    append(cases, &case_count, raw_cases[i]);
  }
  const uint32_t thresholds[] = {OVERFLOW_FIRST, ZERO_LAST, SUBNORMAL_LAST};
  for (unsigned i = 0; i < 3; ++i) {
    for (int delta = -2; delta <= 2; ++delta) {
      append(cases, &case_count, thresholds[i] + (uint32_t)delta);
    }
  }
  fenv_t saved;
  if (feholdexcept(&saved) != 0) {
    fputs("expf-special: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0;
  if (fesetenv(FE_DFL_ENV) != 0) {
    fputs("expf-special: cannot select default floating environment\n", stderr);
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
        else if (a == INF) {
          expected = (word & SIGN) ? 0 : INF;
        }
        else if (a == 0) {
          expected = ONE;
        }
        else if ((word & SIGN) == 0 && word >= OVERFLOW_FIRST) {
          expected = INF;
          required = FE_OVERFLOW | FE_INEXACT;
        }
        else if ((word & SIGN) != 0 && word >= ZERO_LAST) {
          required = FE_UNDERFLOW | FE_INEXACT;
        }
        else {
          exact = 0;
          required = FE_INEXACT;
          if ((word & SIGN) != 0 && word >= SUBNORMAL_LAST) {
            required |= FE_UNDERFLOW;
          }
          if (m == 0 && a <= 0x32800000u) {
            expected = ONE;
            exact = 1;
          }
        }
        float argument;
        memcpy(&argument, &word, sizeof argument);
        if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[s]) != 0) {
          ++failures;
          goto done;
        }
        int existing = fetestexcept(FE_ALL_EXCEPT);
        errno = E2BIG;
        float result = gmath_expf(argument);
        int result_errno = errno;
        int result_flags = fetestexcept(FE_ALL_EXCEPT), result_mode = fegetround();
        uint32_t result_word;
        memcpy(&result_word, &result, sizeof result_word);
        int bad_result = exact ? result_word != expected :
            ((result_word & SIGN) != 0 || result_word >= INF ||
             ((required & FE_UNDERFLOW) == 0 && result_word == 0));
        if (!exact && m == 0) {
          if ((required & FE_UNDERFLOW) != 0) {
            bad_result |= result_word == 0 || result_word >= MIN_NORMAL;
          }
          else {
            bad_result |= result_word < MIN_NORMAL;
          }
        }
        int needed = required | existing;
        if (bad_result || (result_flags & needed) != needed ||
            (result_flags & ~needed) != 0 || result_errno != E2BIG || result_mode != modes[m]) {
          if (failures < 20) {
            fprintf(stderr, "expf-special: input=%08" PRIx32 " result=%08" PRIx32
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
    fputs("expf-special: cannot restore floating environment\n", stderr);
    ++failures;
  }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.expf_special.hash %016" PRIx64 "\n", hash);
    printf("math.expf_special.count %" PRIu64 "\n", count);
  }
  else {
    fprintf(stderr, "expf-special: %u contract checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
