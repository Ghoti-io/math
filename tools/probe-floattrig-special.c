/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw binary32 trig contracts without gtest or float-return constructors.
 * The hash covers only nearest-mode calls without incoming exception flags.
 * Ordinary finite accuracy is tested only in nearest mode; other modes still
 * require finite nonzero results of the expected sign and preserved state.
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

_Static_assert(CHAR_BIT == 8 && sizeof(float) == 4 &&
    sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
    FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128 && sizeof(double) == 8 &&
    DBL_MANT_DIG == 53 && DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
    "raw float trig probe requires IEEE binary32 in eight-bit bytes");

static const uint32_t words[] = {
    0, SIGN, INF, INF | SIGN,
    QNAN, QNAN | 7, 0x7fffffffu,
    QNAN | SIGN, QNAN | SIGN | 7, 0xffffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u,
    INF | SIGN | 1, INF | SIGN | (QUIET - 1), INF | SIGN | 0x12345u,
    1, 0x00400000u, 0x007fffffu, SIGN | 1, SIGN | 0x00400000u, SIGN | 0x007fffffu,
    0x00800000u, 0x80800000u, 0x3f7fffffu, 0x3f800000u, 0x3f800001u, 0xbf7fffffu, 0xbf800000u, 0xbf800001u};
static const struct {
  const char * name;
  float (*call)(float);
} functions[] = {{"sinf", gmath_sinf}, {"cosf", gmath_cosf}, {"tanf", gmath_tanf}};

/* Nearest results and signed true-ULP errors copied from the committed
 * sinf/cosf/tanf corpora: MPFR 4.2.2, gmpy2 2.3.2, mpmath 1.4.1.
 * These are one-ulp references, not exact-bit requirements for finite calls. */
static const struct reference {
  uint32_t input, result[3], error[3];
} references[] = {
    {0x00800000u, {0x00800000u, 0x3f800000u, 0x00800000u}, {0x80000000u, 0x80000000u, 0x00000000u}},
    {0x80800000u, {0x80800000u, 0x3f800000u, 0x80800000u}, {0x00000000u, 0x80000000u, 0x80000000u}},
    {0x3f7fffffu, {0x3f576aa4u, 0x3f0a5141u, 0x3fc75921u}, {0xbd9046ccu, 0x3eaa25b1u, 0x3e3dfee5u}},
    {0x3f800000u, {0x3f576aa4u, 0x3f0a5140u, 0x3fc75923u}, {0x3ef090cfu, 0x3efb5069u, 0xbdd04717u}},
    {0x3f800001u, {0x3f576aa6u, 0x3f0a513fu, 0x3fc75926u}, {0xbee62a33u, 0xbe44b457u, 0x3ea5cbeau}},
    {0xbf7fffffu, {0xbf576aa4u, 0x3f0a5141u, 0xbfc75921u}, {0x3d9046ccu, 0x3eaa25b1u, 0xbe3dfee5u}},
    {0xbf800000u, {0xbf576aa4u, 0x3f0a5140u, 0xbfc75923u}, {0xbef090cfu, 0x3efb5069u, 0x3dd04717u}},
    {0xbf800001u, {0xbf576aa6u, 0x3f0a513fu, 0xbfc75926u}, {0x3ee62a33u, 0xbe44b457u, 0xbea5cbeau}},
};
/* Call only after capturing the tested operation's flags, errno and mode.
 * Half a binary32 ULP of the stored error is below 2^-24; the final check
 * adds that conservative error-word uncertainty before applying the one-ulp bound. */
static double reference_error(uint32_t got, uint32_t reference, uint32_t error) {
  float g, r, e;
  memcpy(&g, &got, sizeof g);
  memcpy(&r, &reference, sizeof r);
  memcpy(&e, &error, sizeof e);
  int unit_exponent = (int)((reference & ABS) >> 23) - 150;
  if ((reference & 0x007fffffu) == 0 && ((reference ^ error) & SIGN) != 0) {
    --unit_exponent;
  }
  if (unit_exponent < -149) {
    unit_exponent = -149;
  }
  uint64_t unit_bits = (uint64_t)(1023 + unit_exponent) << 52;
  double unit;
  memcpy(&unit, &unit_bits, sizeof unit);
  double delta = ((double)g - (double)r) / unit - (double)e;
  return delta < 0 ? -delta : delta;
}
/* Portable bits, independent of the target's FE_* numeric values. */
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
  /* An opaque call prevents metric arithmetic from being speculated across
   * the tested call and its floating-environment snapshot. */
  double (*volatile metric)(uint32_t, uint32_t, uint32_t) = reference_error;
  fenv_t saved;
  int saved_errno = errno;
  if (feholdexcept(&saved) != 0) {
    fputs("floattrig-special: cannot save floating environment\n", stderr);
    errno = saved_errno;
    return 1;
  }
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
      FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT};
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0;
  for (unsigned m = 0; m < sizeof modes / sizeof modes[0]; ++m) {
    if (fesetround(modes[m]) != 0) {
      fputs("floattrig-special: cannot select rounding mode\n", stderr);
      ++failures;
      goto done;
    }
    for (unsigned s = 0; s < sizeof seeds / sizeof seeds[0]; ++s) {
      for (unsigned f = 0; f < sizeof functions / sizeof functions[0]; ++f) {
        for (unsigned i = 0; i < sizeof words / sizeof words[0]; ++i) {
          uint32_t word = words[i], magnitude = word & ABS;
          const struct reference * reference = NULL;
          for (unsigned j = 0; j < sizeof references / sizeof references[0]; ++j) {
            if (references[j].input == word) {
              reference = &references[j];
              break;
            }
          }
          uint32_t expected;
          int required = 0, allowed = 0;
          if (reference != NULL) {
            expected = reference->result[f];
            allowed = FE_INEXACT;
          }
          else if (magnitude >= INF) {
            expected = QNAN;
            if (magnitude == INF || (magnitude & QUIET) == 0) {
              required = FE_INVALID;
            }
          }
          else if (f == 1) {
            expected = ONE;
            if (magnitude != 0) {
              allowed = FE_INEXACT; /* Tiny cos must never acquire underflow. */
            }
          }
          else {
            expected = word;
            if (magnitude != 0) {
              required = FE_UNDERFLOW | FE_INEXACT;
            }
          }
          if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[s]) != 0) {
            fputs("floattrig-special: cannot prepare incoming flags\n", stderr);
            ++failures;
            goto done;
          }
          int existing = fetestexcept(FE_ALL_EXCEPT);
          float input;
          memcpy(&input, &word, sizeof input);
          errno = E2BIG;
          float result = functions[f].call(input);
          int result_errno = errno;
          int result_flags = fetestexcept(FE_ALL_EXCEPT);
          int result_mode = fegetround();
          uint32_t result_word;
          memcpy(&result_word, &result, sizeof result_word);
          int bad_result = result_word != expected;
          double error = 0;
          if (reference != NULL) {
            uint32_t result_magnitude = result_word & ABS;
            bad_result = result_magnitude == 0 || result_magnitude >= INF ||
                ((result_word ^ expected) & SIGN) != 0;
            if (result_magnitude < 0x00800000u) {
              required |= FE_UNDERFLOW | FE_INEXACT;
              allowed |= FE_UNDERFLOW;
            }
            if (m == 0 && !bad_result) {
              error = metric(result_word, expected, reference->error[f]);
              bad_result = error + 0x1p-24 > 1.0;
            }
          }
          int needed = required | existing;
          if (bad_result || (result_flags & needed) != needed ||
              (result_flags & ~(needed | allowed)) != 0 || result_errno != E2BIG ||
              result_mode != modes[m]) {
            if (failures < 20) {
              fprintf(stderr, "floattrig-special: %s(%08" PRIx32 ")=%08" PRIx32
                  " expected=%08" PRIx32 " flags=%x required=%x allowed=%x"
                  " errno=%d mode=%x expected-mode=%x error-ulp=%g\n", functions[f].name,
                  word, result_word, expected, (unsigned)result_flags,
                  (unsigned)needed, (unsigned)allowed, result_errno,
                  (unsigned)result_mode, (unsigned)modes[m], error);
            }
            ++failures;
          }
          if (m == 0 && s == 0) {
            hash = hash_word(hash, result_word);
            hash = hash_word(hash, normalized_flags(result_flags & ~(allowed & ~required)));
            ++count;
          }
        }
      }
    }
  }
 done:
  /* Restore before emitting a result so even an observing caller sees its
   * own mode, flags and trap configuration during output. */
  if (fesetenv(&saved) != 0) {
    fputs("floattrig-special: cannot restore floating environment\n", stderr);
    ++failures;
  }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.floattrig_special.hash %016" PRIx64 "\n", hash);
    printf("math.floattrig_special.count %" PRIu64 "\n", count);
  }
  else {
    fprintf(stderr, "floattrig-special: %u contract checks failed\n", failures);
  }
  errno = saved_errno;
  return failures != 0;
}
