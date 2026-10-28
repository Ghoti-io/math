/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact current-mode integer conversion from unsigned IEEE fields.
 */
#include <ghoti.io/math/macros.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include "nearby_mode.h"
#include <float.h>
#include <limits.h>

GMATH_STATIC_ASSERT((LONG_MAX == INT32_MAX || LONG_MAX == INT64_MAX) &&
    LONG_MIN == -LONG_MAX - 1, "lrint requires signed32/64 long");
GMATH_STATIC_ASSERT(LLONG_MAX == INT64_MAX && LLONG_MIN == -LLONG_MAX - 1,
    "llrint requires signed64 long long");
GMATH_STATIC_ASSERT(sizeof(double) == sizeof(uint64_t) && FLT_RADIX == 2 &&
    DBL_MANT_DIG == 53 && DBL_MIN_EXP == -1021 && DBL_MAX_EXP == 1024,
    "lrint requires IEEE binary64");
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
    FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
    "lrintf requires IEEE binary32");

static int64_t ci_invalid(uint64_t maximum) {
  (void)gmath_invalid();
  return -(int64_t)maximum - 1;
}
static void ci_inexact(void) {
  volatile double one = 1.0, tiny = 0x1p-54;
  volatile double result = one + tiny;
  (void)result;
}
static int64_t ci_round(uint64_t word, unsigned p, unsigned eb,
    unsigned bias, uint64_t maximum) {
  uint64_t sign = word >> (p + eb);
  uint64_t a = word & ((UINT64_C(1) << (p + eb)) - 1);
  uint64_t limit = (uint64_t)(bias + 63) << p;
  /* Larger values are integral or nonfinite; do not narrow or shift first. */
  if (a >= limit) {
    if (a == limit && sign && maximum == INT64_MAX) {
      return INT64_MIN;
    }
    return ci_invalid(maximum);
  }
  if (!a) {
    return 0;
  }
  uint64_t magnitude = 0, fraction = a, halfway = (uint64_t)(bias - 1) << p;
  if (a >= ((uint64_t)bias << p)) {
    unsigned exponent = (unsigned)(a >> p) - bias;
    uint64_t significand = (a & ((UINT64_C(1) << p) - 1)) |
        (UINT64_C(1) << p);
    if (exponent >= p) {
      magnitude = significand << (exponent - p); /* At most62-p. */
      fraction = 0;
    }
    else {
      unsigned cut = p - exponent; /* 1..p. */
      magnitude = significand >> cut;
      fraction = significand & ((UINT64_C(1) << cut) - 1);
      halfway = UINT64_C(1) << (cut - 1);
    }
  }
  if (fraction) {
    int mode = nearby_mode();
    unsigned increment;
    if (mode == 2) {
      increment = !sign;
    }
    else if (mode == 1) {
      increment = (unsigned)sign;
    }
    else if (mode == 3) {
      increment = 0;
    }
    else {
      increment = fraction > halfway ||
          (fraction == halfway && (magnitude & 1));
    }
    magnitude += increment;
  }
  if (magnitude > maximum + sign) {
    return ci_invalid(maximum);
  }
  if (fraction) {
    ci_inexact();
  }
  if (sign && magnitude == maximum + 1) {
    return -(int64_t)maximum - 1;
  }
  return sign ? -(int64_t)magnitude : (int64_t)magnitude;
}
static uint64_t ci_float_bits(float x) {
  uint32_t word;
  memcpy(&word, &x, sizeof word);
  return word;
}
long gmath_lrint(double x) {
  return (long)ci_round(gmath_bits(x), 52, 11, 1023, LONG_MAX);
}
long gmath_lrintf(float x) {
  return (long)ci_round(ci_float_bits(x), 23, 8, 127, LONG_MAX);
}
long long gmath_llrint(double x) {
  return (long long)ci_round(gmath_bits(x), 52, 11, 1023, LLONG_MAX);
}
long long gmath_llrintf(float x) {
  return (long long)ci_round(ci_float_bits(x), 23, 8, 127, LLONG_MAX);
}
