/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Oracle-free raw binary32 exp2 contracts. Only exact powers, zeros, special
 * values, classified tails and nearest tiny inputs have exact-bit expectations.
 * All state is captured before output or any reference arithmetic.
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
    "raw exp2f probe requires IEEE binary32 in eight-bit bytes");

static const uint32_t raw_cases[] = {
    0, SIGN, INF, INF | SIGN,
    QNAN, QNAN | 7, 0x7fffffffu, QNAN | SIGN, QNAN | SIGN | 7, 0xffffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u,
    INF | SIGN | 1, INF | SIGN | (QUIET - 1), INF | SIGN | 0x12345u,
    1, SIGN | 1, 0x007fffffu, 0x807fffffu, MIN_NORMAL, SIGN | MIN_NORMAL,
    0x327fffffu, 0xb27fffffu, 0x32800000u, 0xb2800000u,
    0x32800001u, 0xb2800001u, 0x3f000000u, 0xbf000000u,
    0x42fbffffu, 0x42fc0000u, 0x42fc0001u,
    0xc2fbffffu, 0xc2fc0000u, 0xc2fc0001u,
    0x42ffffffu, 0x43000000u, 0x43000001u,
    0xc314ffffu, 0xc3150000u, 0xc3150001u,
    0xc315ffffu, 0xc3160000u, 0xc3160001u,
    0x7f7fffffu, 0xff7fffffu};

static uint32_t integer_word(int n) {
  uint32_t sign = n < 0 ? SIGN : 0;
  unsigned magnitude = (unsigned)(n < 0 ? -n : n);
  if (magnitude == 0) {
    return sign;
  }
  unsigned leading = 0, scan = magnitude;
  while ((scan >>= 1) != 0) {
    ++leading;
  }
  return sign | ((leading + 127u) << 23) |
      (((uint32_t)magnitude << (23u - leading)) & 0x007fffffu);
}
static void append(uint32_t * cases, unsigned * count, uint32_t word) {
  for (unsigned i = 0; i < *count; ++i) {
    if (cases[i] == word) {
      return;
    }
  }
  cases[(*count)++] = word;
}
/* Called only inside (-150,128), so every relevant integer fits in eight bits. */
static int integer_value(uint32_t word, int * n) {
  uint32_t a = word & ABS;
  if (a == 0) {
    *n = 0;
    return 1;
  }
  int exponent = (int)(a >> 23) - 127;
  if (exponent < 0 || exponent > 7) {
    return 0;
  }
  unsigned shift = 23u - (unsigned)exponent;
  uint32_t significand = (a & 0x007fffffu) | 0x00800000u;
  if ((significand & ((1u << shift) - 1u)) != 0) {
    return 0;
  }
  int value = (int)(significand >> shift);
  *n = (word & SIGN) ? -value : value;
  return 1;
}
static uint32_t power_word(int n) {
  return n < -126 ? 1u << (unsigned)(n + 149) : (uint32_t)(n + 127) << 23;
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
  uint32_t cases[sizeof raw_cases / sizeof raw_cases[0] + 277];
  unsigned case_count = 0;
  for (unsigned i = 0; i < sizeof raw_cases / sizeof raw_cases[0]; ++i) {
    append(cases, &case_count, raw_cases[i]);
  }
  for (int n = -149; n <= 127; ++n) {
    append(cases, &case_count, integer_word(n));
  }
  fenv_t saved;
  if (feholdexcept(&saved) != 0) {
    fputs("exp2f-special: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0;
  if (fesetenv(FE_DFL_ENV) != 0) {
    fputs("exp2f-special: cannot select default floating environment\n", stderr);
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
        int required = 0, exact = 1, n;
        if (a > INF) {
          expected = QNAN;
          required = (a & QUIET) == 0 ? FE_INVALID : 0;
        }
        else if (a == INF) {
          expected = (word & SIGN) ? 0 : INF;
        }
        else if ((word & SIGN) == 0 && a >= 0x43000000u) {
          expected = INF;
          required = FE_OVERFLOW | FE_INEXACT;
        }
        else if ((word & SIGN) != 0 && a >= 0x43160000u) {
          required = FE_UNDERFLOW | FE_INEXACT;
        }
        else if (integer_value(word, &n)) {
          expected = power_word(n);
        }
        else {
          exact = 0;
          required = FE_INEXACT;
          if ((word & SIGN) != 0 && a > 0x42fc0000u) {
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
        float result = gmath_exp2f(argument);
        int result_errno = errno;
        int result_flags = fetestexcept(FE_ALL_EXCEPT), result_mode = fegetround();
        uint32_t result_word;
        memcpy(&result_word, &result, sizeof result_word);
        int bad_result = exact ? result_word != expected :
            ((result_word & SIGN) != 0 || result_word >= INF ||
             ((required & FE_UNDERFLOW) == 0 && result_word < MIN_NORMAL));
        if (!exact && m == 0 && (required & FE_UNDERFLOW) != 0) {
          bad_result |= result_word >= MIN_NORMAL;
        }
        int needed = required | existing;
        if (bad_result || (result_flags & needed) != needed ||
            (result_flags & ~needed) != 0 || result_errno != E2BIG || result_mode != modes[m]) {
          if (failures < 20) {
            fprintf(stderr, "exp2f-special: input=%08" PRIx32 " result=%08" PRIx32
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
    fputs("exp2f-special: cannot restore floating environment\n", stderr);
    ++failures;
  }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.exp2f_special.hash %016" PRIx64 "\n", hash);
    printf("math.exp2f_special.count %" PRIu64 "\n", count);
  }
  else {
    fprintf(stderr, "exp2f-special: %u contract checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
